"""Shared adapter seam matches legacy records on stable fixtures."""
from pathlib import Path
import pytest
import production_calibration_adapter as adapter
from cohort_validation import POLICY
import test_production_calibration_adapter as fixtures

@pytest.mark.parametrize('kind',['public','reference','mixed'])
def test_explicit_shared_seam_matches_legacy_records(tmp_path,kind):
 helper=fixtures.Adapter();manifest,cell,_=helper.mixed(tmp_path) if kind=='mixed' else helper.build(tmp_path,public=kind=='public')
 expected=[str(tmp_path/'worker.py')]
 legacy=adapter.normalize(manifest)
 result=adapter.normalize_shared([manifest],policy=POLICY,expected_inventory=expected,inventory=lambda:expected)
 assert result['shared_validation_passed'] and result['records']==legacy

def test_shared_failure_has_complete_record_schema_and_cost(tmp_path):
 manifest,cell,_=fixtures.Adapter().build(tmp_path,public=True);source=tmp_path/'worker.py';source.write_text('changed')
 result=adapter.normalize_shared([manifest],policy=POLICY,expected_inventory=[str(source)],inventory=lambda:[str(source)])
 row=result['records'][0]
 assert not row['usable'] and not row['provenance_valid'] and row['intervals']=={}
 for field in ('model','arm','procedure_sha256','dataset_seed','source_sha256','fixture_sha256','truth','protocol_sha256','normalization','original_report_sha256'):assert field in row
 assert row['cost']['controller_seconds'] is not None



def test_direct_internal_seam_cannot_admit_before_finish(tmp_path):
 from cohort_validation import SharedValidation
 manifest,cell,_=fixtures.Adapter().build(tmp_path,public=True);source=str(tmp_path/'worker.py')
 context=SharedValidation([manifest['procedure']['bound_files']],lambda:[source],[source]);context.begin()
 row=adapter.normalize_cell(manifest,cell,shared_context=context)
 assert row['shared_validation_provisional'] and not row['usable'] and not row['provenance_valid']
 assert row['shared_validation_pending_flags']['usable'] is True
