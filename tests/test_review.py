"""Kiểm tra số tính tay, đồng điểm, null và lỗi cố ý của audit độc lập."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from maintenance.review import independent_metrics, compare_values, load_verified_package, audit_frames, FEATURES


class IndependentReviewTests(unittest.TestCase):
    def fixture(self):
        import pandas as pd
        readings=pd.DataFrame({'dataset_version':['v']*4,'reading_id':[1,2,3,4],'machine_failure':[1,0,1,0]})
        runs=pd.DataFrame([{'model_run_id':'r','split_id':'s','model_family':'random','feature_set':'none','seed':42,'threshold':.5}])
        membership=readings[['dataset_version','reading_id']].assign(split_id='s',split=['validation','validation','test','test'])
        scores=membership.assign(model_run_id='r',model_family='random',feature_set='none',priority_score=[.8,.2,.8,.2],predicted_failure=[1,0,1,0],priority_rank=[1,2,1,2])
        metrics=[]; budgets=[]
        for split,ids in [('validation',[1,2]),('test',[3,4])]:
            m=independent_metrics([1,0],[.8,.2],ids,.5,(1,2))
            metrics.append({'model_run_id':'r','split':split,**m})
            for k in [1,2]:
                budgets.append({'model_run_id':'r','split':split,'budget_k':k,'n_samples':2,'n_failures':1,'topk_applicable':True,
                                'tp':1,'precision':1/k,'recall':1.})
        return {'readings':readings,'model_runs':runs,'split_membership':membership,'scores':scores,
                'metrics':pd.DataFrame(metrics),'budget_metrics':pd.DataFrame(budgets),'features':pd.DataFrame(columns=FEATURES)}

    def test_population_and_rank_corruptions_are_detected(self):
        frames=self.fixture()
        self.assertEqual(len(audit_frames(frames,(1,2))[0]),2)
        frames['scores']=frames['scores'].iloc[1:].copy()
        with self.assertRaisesRegex(ValueError,'quần thể'):
            audit_frames(frames,(1,2))
        frames=self.fixture(); frames['scores'].loc[0,'priority_rank']=2
        with self.assertRaisesRegex(ValueError,'Rank'):
            audit_frames(frames,(1,2))

    def test_wrong_predictions_and_leaking_features_fail(self):
        frames=self.fixture(); frames['scores'].loc[0,'predicted_failure']=0
        with self.assertRaisesRegex(ValueError,'ngưỡng'):
            audit_frames(frames,(1,2))
        frames=self.fixture(); frames['features']['machine_failure']=[]
        with self.assertRaisesRegex(ValueError,'Feature'):
            audit_frames(frames,(1,2))

    def test_hand_calculated_matrix_and_continuous_auc(self):
        m=independent_metrics([1,0,1,0],[.9,.8,.2,.1],[1,2,3,4],.5,(2,))
        self.assertEqual([m[k] for k in ['tp','fp','fn','tn']],[1,1,1,1])
        self.assertEqual((m['precision'],m['recall'],m['f1']),(.5,.5,.5))
        self.assertAlmostEqual(m['roc_auc'],.75)
        self.assertAlmostEqual(m['average_precision'],5/6)

    def test_tied_scores_use_id_and_topk_is_global(self):
        m=independent_metrics([1,0,1],[.9,.9,.1],[20,10,30],.5,(1,2))
        self.assertEqual(m['tp_at_1'],0)
        self.assertEqual(m['tp_at_2'],1)

    def test_empty_positive_and_oversized_budget_not_zero(self):
        m=independent_metrics([0,0],[.2,.1],[1,2],1.,(3,))
        for k in ['precision','recall','f1','roc_auc','average_precision','tp_at_3']:
            self.assertIsNone(m[k])
        self.assertFalse(m['recall_defined'])
        self.assertFalse(m['k_3_available'])

    def test_bad_vectors_and_duplicate_ids_rejected(self):
        for args in [([],[],[],.5),([1,0],[.2,.1],[1,1],.5),([1,2],[.2,.1],[1,2],.5)]:
            with self.assertRaises(ValueError):
                independent_metrics(*args)

    def test_corrupt_metrics_and_null_are_detected(self):
        good={'tp':2,'precision':None}
        with self.assertRaisesRegex(ValueError,'tp'):
            compare_values(good,{'tp':3,'precision':None},good,'fixture')
        with self.assertRaisesRegex(ValueError,'precision'):
            compare_values(good,{'tp':2,'precision':0.},good,'fixture')

    def test_hash_corruption_detected_before_loading(self):
        import hashlib,json
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); (root/'data/metadata').mkdir(parents=True)
            package=root/'csv'; package.mkdir()
            (package/'x.csv').write_text('x\n2\n',encoding='utf-8')
            original=hashlib.sha256(b'x\n1\n').hexdigest()
            (root/'data/metadata/handoff.json').write_text(json.dumps({'files':[{'path':'x.csv','sha256':original}]}))
            with self.assertRaisesRegex(ValueError,'SHA256'):
                load_verified_package(root,package)
