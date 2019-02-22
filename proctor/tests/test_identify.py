from contextlib import contextmanager

import mock
from django.conf import settings
from mock import ANY

from proctor import api
from proctor import cache
from proctor import identify


class TestIdentifyGroups:

    def test_requested_group_resolved(self):
        params = create_proctor_parameters({'account': 1234}, defined_tests=['fake_proctor_test'])
        mock_requests = mock_http_get_data({'fake_proctor_test': {'name': 'active', 'value': 1}})

        # When
        groups = identify.identify_groups(params, http=mock_requests)

        # Then
        mock_requests.get.assert_called_once_with(
            'fake-proctor-api-url/groups/identify',
            params={'id.account': 1234, 'ctx.ua': '', 'test': 'fake_proctor_test'},
            timeout=ANY,
        )
        assert groups.fake_proctor_test.value == 1
        assert groups.fake_proctor_test.group == 'active'

    def test_cached_result_used(self):
        params = create_proctor_parameters({'account': 1234}, defined_tests=['fake_proctor_test'])
        mock_requests = mock_http_get_data({'fake_proctor_test': {'name': 'active', 'value': 1}})
        cacher = cache.CacheCacher()

        # When called twice
        identify.identify_groups(params, cacher=cacher, http=mock_requests)
        identify.identify_groups(params, cacher=cacher, http=mock_requests)

        # Then request only made once
        mock_requests.get.assert_called_once()

    def test_response_has_no_group_data(self):
        params = create_proctor_parameters({})
        mock_requests = mock_http_get_json({'data': {}})

        # When
        with patch_python_logger() as mock_logger:
            identify.identify_groups(params, http=mock_requests)

        # Then
        mock_logger.error.assert_called_once_with(ANY, ANY, 'missing groups field', ANY)

    def test_api_error_message(self):
        params = create_proctor_parameters({})
        mock_requests = mock_http_get_data(
            group_data={},
            added_data={'meta': {'error': 'scary message'}},
            status_code=500,
        )

        # When
        with patch_python_logger() as mock_logger:
            identify.identify_groups(params, http=mock_requests)

        # Then
        mock_logger.error.assert_called_once_with(ANY, ANY, ANY, ANY, 'scary message')


class TestProcByAccountid:

    def test_fake_proctor_test_not_found(self):
        groups = identify.proc_by_accountid(1234)
        assert groups.fake_proctor_test_in_settings.value is None
        assert groups.fake_proctor_test_in_settings.group is None


# TODO: This function can probably be removed to `api` or `identify` module
def create_proctor_parameters(identifier_dict, defined_tests=None):
    if defined_tests is None:
        defined_tests = settings.PROCTOR_TESTS

    params = api.ProctorParameters(
        api_root=settings.PROCTOR_API_ROOT,
        defined_tests=defined_tests,
        context_dict={'ua': ''},
        identifier_dict=identifier_dict,
        force_groups=None,
    )
    return params


def mock_http_get_data(group_data=None, added_data=None, status_code=200):
    json_data = {
        'data': {
            'groups': group_data,
            'audit': {'version': "1"},
        },
    }

    if added_data:
        json_data.update(added_data)

    return mock_http_get_json(json_data, status_code=status_code)


def mock_http_get_json(json_data, status_code=200):
    mock_response = mock.Mock(status_code=status_code)
    mock_response.json.return_value = json_data

    mock_requests = mock.Mock()
    mock_requests.get.return_value = mock_response

    return mock_requests


@contextmanager
def patch_python_logger():
    with mock.patch.object(api, 'logger') as mock_logger:
        yield mock_logger
