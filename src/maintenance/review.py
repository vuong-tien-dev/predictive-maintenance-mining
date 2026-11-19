"""Kiểm chứng hậu kiểm độc lập từ CSV; không gọi mã metrics hoặc fit v1."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

KEYS = ['dataset_version', 'reading_id']
FEATURES = [*KEYS, 'product_type', 'air_temperature_k', 'process_temperature_k',
            'rotational_speed_rpm', 'torque_nm', 'tool_wear_min',
            'temperature_difference_k', 'power_w', 'wear_torque_min_nm']


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def independent_metrics(y, scores, ids, threshold, budgets=(20, 50, 100)):
    """Ma trận đếm trực tiếp; thứ hạng stable theo score rồi ID, null có ngữ nghĩa."""
    frame = pd.DataFrame({'y': y, 'score': scores, 'id': ids})
    if frame.empty or frame.isna().any().any() or frame.id.duplicated().any():
        raise ValueError('Vector rỗng, null hoặc ID trùng.')
    if not frame.y.isin([0, 1]).all() or not np.isfinite(frame.score).all() or not np.isfinite(threshold):
        raise ValueError('Nhãn/điểm/ngưỡng không hợp lệ.')
    if any(not isinstance(k, int) or isinstance(k, bool) or k < 1 for k in budgets):
        raise ValueError('Ngân sách cần số nguyên dương.')
    predicted = frame.score.ge(threshold)
    tp = int((frame.y.eq(1) & predicted).sum())
    fp = int((frame.y.eq(0) & predicted).sum())
    fn = int((frame.y.eq(1) & ~predicted).sum())
    tn = int((frame.y.eq(0) & ~predicted).sum())
    failures = int(frame.y.sum())
    result = {'n_samples': len(frame), 'n_failures': failures, 'threshold': float(threshold),
              'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn,
              'precision': tp/(tp+fp) if tp+fp else None,
              'recall': tp/failures if failures else None,
              'f1': 2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None,
              'precision_defined': bool(tp+fp), 'recall_defined': bool(failures),
              'f1_defined': bool(2*tp+fp+fn),
              'roc_auc': float(roc_auc_score(frame.y, frame.score)) if frame.y.nunique()==2 else None,
              'average_precision': float(average_precision_score(frame.y, frame.score)) if failures else None}
    order = frame.sort_values(['score', 'id'], ascending=[False, True], kind='stable')
    for k in budgets:
        ok = k <= len(order)
        hits = int(order.head(k).y.sum()) if ok else None
        result[f'tp_at_{k}'] = hits
        result[f'precision_at_{k}'] = hits/k if ok else None
        result[f'recall_at_{k}'] = hits/failures if ok and failures else None
        result[f'k_{k}_available'] = ok
    return result


def compare_values(actual, expected, fields, context):
    """Bắt sai số thực hoặc null/defined khác nghĩa, không tự sửa kết quả tham chiếu."""
    for field in fields:
        x, y = actual[field], expected[field]
        if pd.isna(x) or pd.isna(y):
            equal = pd.isna(x) and pd.isna(y)
        elif isinstance(x, (bool, np.bool_)) or isinstance(y, (bool, np.bool_)):
            equal = x == y
        elif isinstance(x, (int, float, np.number)):
            equal = bool(np.isclose(float(x), float(y), rtol=1e-10, atol=1e-12))
        else:
            equal = x == y
        if not equal:
            raise ValueError(f'{context}: {field} khác tham chiếu ({x!r} / {y!r}).')


def load_verified_package(root, package=None):
    """Kiểm tra độc lập tám file theo manifest đã theo dõi trong Git."""
    root = Path(root).resolve()
    package = Path(package).resolve() if package else root/'data/processed/handoff-v1'
    manifest = json.loads((root/'data/metadata/handoff.json').read_text(encoding='utf-8'))
    tables, checks = {}, []
    for entry in manifest['files']:
        path = package/Path(entry['path']).name
        if digest(path) != entry['sha256']:
            raise ValueError(f'Sai SHA256: {path.name}')
        frame = pd.read_csv(path)
        columns = [c['name'] for c in entry['columns']]
        if list(frame.columns) != columns or len(frame) != entry['rows']:
            raise ValueError(f'Sai schema/số dòng: {path.name}')
        if frame.duplicated(entry['primary_key']).any():
            raise ValueError(f'Trùng khóa: {path.name}')
        for column in entry['columns']:
            values = frame[column['name']]
            if not column['nullable'] and values.isna().any():
                raise ValueError(f'Null ngoài hợp đồng: {path.name}/{column["name"]}')
            kind = column['pandas_dtype']
            if kind.startswith('int') and (not pd.api.types.is_integer_dtype(values.dtype)):
                raise ValueError(f'Sai kiểu integer: {path.name}/{column["name"]}')
            if kind == 'bool' and not pd.api.types.is_bool_dtype(values.dtype):
                raise ValueError(f'Sai kiểu bool: {path.name}/{column["name"]}')
        tables[entry['table']] = frame
        checks.append({'table': entry['table'], 'rows': len(frame), 'sha256': digest(path),
                       'hash_schema_key_null_checks': 'PASS'})
    if len(tables) != 8:
        raise ValueError('Cần đúng tám bảng bàn giao.')
    return tables, pd.DataFrame(checks)


def audit_frames(tables, budgets=(20, 50, 100)):
    """Đối chiếu mọi run/partition, quần thể, ngưỡng và ngân sách từ điểm lưu."""
    readings, runs, mapping = (tables[name] for name in ['readings', 'model_runs', 'split_membership'])
    scores, metrics, stored_budgets = (tables[name] for name in ['scores', 'metrics', 'budget_metrics'])
    if list(tables['features'].columns) != FEATURES:
        raise ValueError('Feature chứa nhãn/ID không được phép hoặc khác danh sách đã khóa.')
    if readings.duplicated(KEYS).any() or runs.model_run_id.duplicated().any():
        raise ValueError('Trùng khóa đọc/run.')
    if scores.duplicated(['model_run_id', 'split', *KEYS]).any():
        raise ValueError('Trùng score grain.')
    expected_pairs = {(str(r), s) for r in runs.model_run_id for s in ['validation', 'test']}
    if set(zip(scores.model_run_id, scores['split'])) != expected_pairs:
        raise ValueError('Thiếu/thừa run hoặc partition trong điểm.')
    if set(zip(metrics.model_run_id, metrics['split'])) != expected_pairs or len(metrics)!=len(expected_pairs):
        raise ValueError('Thiếu/trùng hàng metrics.')
    expected_budget_keys = {(r, s, k) for r, s in expected_pairs for k in budgets}
    if set(zip(stored_budgets.model_run_id, stored_budgets['split'], stored_budgets.budget_k)) != expected_budget_keys or len(stored_budgets)!=len(expected_budget_keys):
        raise ValueError('Thiếu/trùng ngân sách.')
    output, budget_rows, groups = [], [], []
    for (run_id, partition), part in scores.groupby(['model_run_id', 'split'], sort=True):
        run = runs.set_index('model_run_id').loc[run_id]
        if not part.split_id.eq(run.split_id).all() or not part.model_family.eq(run.model_family).all() or not part.feature_set.eq(run.feature_set).all():
            raise ValueError('Metadata score lệch run.')
        population = mapping.loc[mapping.split_id.eq(run.split_id) & mapping['split'].eq(partition), KEYS]
        actual_keys = set(part[KEYS].itertuples(index=False, name=None))
        if actual_keys != set(population.itertuples(index=False, name=None)) or len(part)!=len(population):
            raise ValueError('Sai quần thể: thiếu/thừa bản ghi của split.')
        joined = part.merge(readings, on=KEYS, validate='many_to_one', indicator=True)
        if not joined['_merge'].eq('both').all() or len(joined)!=len(part):
            raise ValueError('Join nhãn mất hoặc nhân bản bản ghi.')
        joined = joined.sort_values(['priority_score', 'reading_id'], ascending=[False, True], kind='stable')
        if not np.array_equal(joined.priority_rank.to_numpy(), np.arange(1, len(joined)+1)):
            raise ValueError('Rank sai thứ tự score giảm/ID tăng.')
        if not np.array_equal(joined.predicted_failure.to_numpy(), joined.priority_score.ge(run.threshold).astype(int)):
            raise ValueError('Predicted_failure khác ngưỡng đã khóa.')
        result = independent_metrics(joined.machine_failure.to_numpy(), joined.priority_score.to_numpy(),
                                     joined.reading_id.to_numpy(), run.threshold, budgets)
        saved = metrics.loc[metrics.model_run_id.eq(run_id) & metrics['split'].eq(partition)].iloc[0]
        fields = [key for key in result if '_at_' not in key and not key.startswith('k_')]
        compare_values(result, saved, fields, f'{run_id}/{partition}')
        meta = {'model_run_id': run_id, 'split_id': run.split_id, 'split': partition,
                'model_family': run.model_family, 'seed': int(run.seed), 'population_scope': 'all'}
        output.append({**meta, **{key:result[key] for key in fields}, 'check': 'PASS'})
        for k in budgets:
            applicable = run.model_family != 'always_normal'
            values = {'n_samples':len(joined), 'n_failures':result['n_failures'], 'topk_applicable':applicable,
                      'tp': result[f'tp_at_{k}'] if applicable else None,
                      'precision':result[f'precision_at_{k}'] if applicable else None,
                      'recall':result[f'recall_at_{k}'] if applicable else None}
            saved = stored_budgets.loc[stored_budgets.model_run_id.eq(run_id) & stored_budgets['split'].eq(partition) & stored_budgets.budget_k.eq(k)].iloc[0]
            compare_values(values, saved, values.keys(), f'{run_id}/{partition}/k{k}')
            hits = values['tp']
            budget_rows.append({**meta, 'budget_k':k, **values,
                                'fp': k-hits if hits is not None else None,
                                'fn': result['n_failures']-hits if hits is not None else None, 'check':'PASS'})
        if partition=='test' and int(run.seed)==42 and run.model_family in ['isolation_forest','logistic_regression']:
            masks = {f'Type={v}': joined.product_type.eq(v) for v in ['L','M','H']}
            masks.update({f'mode={v}':joined[v].eq(1) for v in ['twf','hdf','pwf','osf','rnf']})
            mode_count = joined[['twf','hdf','pwf','osf','rnf']].sum(axis=1)
            masks.update({'failure_without_mode':joined.machine_failure.eq(1)&mode_count.eq(0),
                          'mode_without_failure':joined.machine_failure.eq(0)&mode_count.gt(0)})
            for name, mask in masks.items():
                sub=joined.loc[mask]
                y=sub.machine_failure.eq(1)
                pred=sub.predicted_failure.eq(1)
                top=sub.priority_rank.le(50)
                failures=int(y.sum())
                groups.append({**meta, 'group':name, 'rows':len(sub), 'n_failures':failures,
                               'tp':int((y&pred).sum()), 'fp':int((~y&pred).sum()),
                               'fn':int((y&~pred).sum()), 'tn':int((~y&~pred).sum()),
                               'global_top50_selected':int(top.sum()), 'global_top50_hits':int((top&y).sum()),
                               'global_top50_recall':int((top&y).sum())/failures if failures else None,
                               'recall_defined':bool(failures)})
    return pd.DataFrame(output), pd.DataFrame(budget_rows), pd.DataFrame(groups)


def audit_package(root, package=None, output=None):
    root=Path(root).resolve()
    output=Path(output) if output else root/'reports/tables/review'
    tables, checks=load_verified_package(root, package)
    metrics, budgets, groups=audit_frames(tables)
    output.mkdir(parents=True, exist_ok=True)
    for name, frame in [('package-checks',checks),('metrics',metrics),('budgets',budgets),('group-errors',groups)]:
        frame.to_csv(output/f'{name}.csv',index=False,float_format='%.17g')
    import platform
    import sklearn
    report={'status':'PASS','scope':'post-hoc independent recomputation; no fitting or selection',
            'package_tables':len(checks),'metric_groups':len(metrics),'budget_groups':len(budgets),
            'platform':platform.platform(),'python':platform.python_version(),
            'pandas':pd.__version__,'numpy':np.__version__,'scikit_learn':sklearn.__version__,
            'audit_source_sha256':digest(__file__),
            'handoff_manifest_sha256':digest(root/'data/metadata/handoff.json'),
            'evaluation_lock_sha256':digest(root/'data/metadata/evaluation-lock.json'),
            'outputs':{p.name:digest(p) for p in sorted(output.glob('*.csv'))}}
    (output/'audit-summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return report


def build_review_figures(root, tables_dir=None):
    """Ba hình tổng hợp từ audit, không ghi dữ liệu cấp bản ghi."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    root=Path(root)
    tables_dir=Path(tables_dir) if tables_dir else root/'reports/tables/review'
    folder=root/'reports/figures/review'
    folder.mkdir(parents=True,exist_ok=True)
    budgets=pd.read_csv(tables_dir/'budgets.csv')
    groups=pd.read_csv(tables_dir/'group-errors.csv')
    primary='ordered-gap100-v1'
    colors={'isolation_forest':'#176B91','logistic_regression':'#D56A25','random':'#777777'}
    fig,ax=plt.subplots(figsize=(7,3.5),layout='constrained')
    for family,color in colors.items():
        part=budgets.loc[budgets.split_id.eq(primary)&budgets['split'].eq('test')&budgets.seed.eq(42)&budgets.model_family.eq(family)].sort_values('budget_k')
        ax.plot(part.budget_k,part.tp,marker='o',label=family,color=color)
    ax.set(xlabel='Inspection budget k',ylabel='Failures found (TP)',xticks=[20,50,100],title='Primary test: 1,900 records, 38 failures, seed 42')
    ax.legend(fontsize=8); ax.grid(alpha=.15)
    fig.savefig(folder/'budget-tradeoff.png',dpi=180); plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(8,3.5),layout='constrained')
    for ax,family in zip(axes,['isolation_forest','logistic_regression']):
        part=groups.loc[groups.split_id.eq(primary)&groups.model_family.eq(family)&groups['group'].str.startswith('Type=')]
        x=np.arange(len(part))
        ax.bar(x-.17,part.fp,width=.34,label='False positive',color='#D56A25')
        ax.bar(x+.17,part.fn,width=.34,label='False negative',color='#176B91')
        ax.set_xticks(x,part['group']); ax.set_title(family,fontsize=10)
        ax.set_ylabel('Records at locked threshold'); ax.legend(fontsize=7)
    fig.savefig(folder/'type-errors.png',dpi=180); plt.close(fig)
    part=budgets.loc[budgets['split'].eq('test')&budgets.seed.eq(42)&budgets.budget_k.eq(50)&budgets.model_family.isin(colors)]
    fig,ax=plt.subplots(figsize=(7,3.5),layout='constrained')
    pivot=part.pivot(index='model_family',columns='split_id',values='recall').reindex(colors)
    pivot.plot.bar(ax=ax,color=['#176B91','#D56A25'],rot=0)
    ax.set(ylabel='Recall@50',xlabel='',title='Same budget, different evaluation populations')
    ax.legend(fontsize=7)
    fig.savefig(folder/'protocol-sensitivity.png',dpi=180); plt.close(fig)
    # Biến dẫn xuất: chỉ dùng bảng validation đã có, không chọn bằng test.
    candidate_rows=[]
    for family,subdir in [('isolation_forest','isolation'),('logistic_regression','classification')]:
        path=root/f'reports/tables/{subdir}/candidates.csv'
        data=pd.read_csv(path)
        for (split,features),part in data.groupby(['split_id','feature_set']):
            best=part.sort_values(['average_precision','precision_at_50','candidate_id'],ascending=[False,False,True]).iloc[0]
            candidate_rows.append({'model_family':family,'split_id':split,'feature_set':features,
                                   'candidate_id':best.candidate_id,'validation_ap':best.average_precision,
                                   'validation_precision_at_50':best.precision_at_50})
    pd.DataFrame(candidate_rows).to_csv(tables_dir/'validation-feature-comparison.csv',index=False)
    return sorted(p.name for p in folder.glob('*.png'))
