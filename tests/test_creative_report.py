import hashlib
import io
import json
from email.message import Message
from types import SimpleNamespace
from unittest.mock import MagicMock
from urllib.error import HTTPError

import pytest

from meta_ads_manager.creative_media import download
from meta_ads_manager.creative_report import checked_file, fmt, render_report
from meta_ads_manager.creative_review import metrics
from meta_ads_manager.errors import AppError


def test_media_redirect_is_revalidated_and_has_no_graph_auth(tmp_path, monkeypatch):
    headers = Message()
    headers['Location'] = 'https://attacker.invalid/private'
    opener = MagicMock()
    opener.open.side_effect = HTTPError('https://fbcdn.net/a', 302, 'redirect', headers,
                                       io.BytesIO())
    monkeypatch.setattr('meta_ads_manager.creative_media.build_opener', lambda _: opener)
    with pytest.raises(AppError, match='CDN'):
        download('https://fbcdn.net/a', tmp_path)
    assert opener.open.call_count == 1
    request = opener.open.call_args.args[0]
    assert request.get_header('Authorization') is None
    assert request.method == 'GET'


def test_evidence_verification_rejects_changed_files_and_escape(tmp_path):
    f = tmp_path / 'data.json'
    f.write_text('original')
    digest = hashlib.sha256(f.read_bytes()).hexdigest()
    assert checked_file(tmp_path, 'data.json', digest) == f
    f.write_text('changed')
    with pytest.raises(AppError, match='zmienił'):
        checked_file(tmp_path, 'data.json', digest)
    with pytest.raises(AppError):
        checked_file(tmp_path, '../data.json', digest)


@pytest.fixture
def report_args(tmp_path):
    scope = {'client_id': 'test', 'account_id': 'act_1', 'since': '2026-08-01',
             'until': '2026-08-30'}
    ad = {'id': '10', 'account_id': '1', 'name': '<script>alert(1)</script>',
          'creative': {'body': '<img src=x onerror=alert(1)>'},
          'campaign': {'name': 'Campaign'}, 'adset': {'name': 'Set',
                                                     'optimization_goal': 'LEAD_GENERATION'}}
    row = {'ad_id': '10', 'spend': '100', 'impressions': '1000', 'actions': [
        {'action_type': 'onsite_conversion.lead_grouped', 'value': '9'}]}
    ad_path = tmp_path / 'ad-10.json'
    ad_path.write_text(json.dumps({'data': ad}))
    digest = hashlib.sha256(ad_path.read_bytes()).hexdigest()
    collection = {**scope, 'selected_ad_ids': ['10'], 'source_hashes': {'ad-10.json': digest},
                  'previous_since': '2026-07-02', 'previous_until': '2026-07-31',
                  'account': {'name': 'Test', 'currency': 'PLN', 'timezone_name': 'Europe/Warsaw'},
                  'cards': [{'ad_id': '10', 'current': metrics(row), 'previous': None}]}
    assessment = {**scope, 'cards': [{'ad_id': '10', 'concept': 'Test', 'content_status': 'partial',
                                    'coverage': 'Text only', 'source_file': 'ad-10.json',
                                    'source_sha256': digest, 'evidence': [],
                                    'observations': ['Observation'], 'hypotheses': ['Hypothesis']}]}
    docs = {'collection.json': collection, 'assessment.json': assessment,
            'ads-current.json': {'data': [row]},
            'media.json': {**scope, 'cards': [{'ad_id': '10', 'assets': []}]},
            'notes.json': {**scope, 'title': 'Test', 'sections': [], 'ad_notes': {}}}
    for name, doc in docs.items():
        (tmp_path / name).write_text(json.dumps(doc))
    return SimpleNamespace(directory=tmp_path, client='test', account='act_1',
                           assessment=tmp_path / 'assessment.json', notes=tmp_path / 'notes.json')


def test_report_escapes_ad_text_and_preserves_unreported_leads(report_args):
    result = render_report(report_args)
    body = report_args.directory.joinpath('report.html').read_text()
    assert result['cards'] == 1
    assert '<script>alert' not in body and '&lt;script&gt;' in body
    assert '<img src=x' not in body and '&lt;img src=x' in body
    assert '100,00' in body
    assert '<dd>—</dd>' in body
    metrics_file = json.loads(report_args.directory.joinpath('report-metrics.json').read_text())
    assert metrics_file['groups']['LEAD_GENERATION']['ads_with_reported_native_leads'] == 0
    assert metrics_file['groups']['LEAD_GENERATION']['reported_native_leads'] is None


def test_cost_rounding_is_consistent_at_half_cent():
    assert fmt('64.205') == '64,21'


@pytest.mark.parametrize('change', ['account', 'period', 'duplicate', 'pending'])
def test_report_rejects_foreign_or_unfinished_assessment(report_args, change):
    doc = json.loads(report_args.assessment.read_text())
    if change == 'account':
        doc['account_id'] = 'act_2'
    elif change == 'period':
        doc['until'] = '2026-08-31'
    elif change == 'duplicate':
        doc['cards'] *= 2
    else:
        doc['cards'][0]['content_status'] = 'pending'
    report_args.assessment.write_text(json.dumps(doc))
    with pytest.raises(AppError):
        render_report(report_args)
    assert not (report_args.directory / 'report.html').exists()


def test_video_frame_preparation_on_synthetic_clip(tmp_path):
    import shutil
    import subprocess

    from meta_ads_manager.creative_media import prepare_frames

    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        pytest.skip('ffmpeg and ffprobe are optional')
    clip = tmp_path / 'synthetic.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                    'color=c=blue:s=160x120:d=1', '-c:v', 'mpeg4', str(clip)],
                   check=True, capture_output=True, timeout=30)
    digest = hashlib.sha256(clip.read_bytes()).hexdigest()
    result = prepare_frames(tmp_path, {'file': clip.name, 'sha256': digest})
    assert result['status'] == 'frames_prepared'
    assert result['duration_seconds'] == pytest.approx(1, abs=.05)
    assert result['frames'] and all((tmp_path / f['file']).is_file() for f in result['frames'])
    assert not result['audio_present']
    assert result['audio_review'] == 'not_reviewed' and result['transcript'] is None
