import unittest
from unittest.mock import patch, MagicMock, call
import os
import sys
import subprocess
import argparse
import requests
from io import StringIO

# Import the module to test
import sbg


class TestParseArgs(unittest.TestCase):
    @patch('sys.argv', ['sbg.py', '--gitlab-url', 'https://gitlab.com',
                        '--token', 'abc123', '--group-ids', 'group1', 'group2',
                        '--dest', '/tmp/backup', '--use-ssh'])
    def test_parse_args_all_options(self):
        args = sbg.parse_args()
        self.assertEqual(args.gitlab_url, 'https://gitlab.com')
        self.assertEqual(args.token, 'abc123')
        self.assertEqual(args.group_ids, ['group1', 'group2'])
        self.assertEqual(args.dest, '/tmp/backup')
        self.assertTrue(args.use_ssh)

    @patch('sys.argv', ['sbg.py', '--gitlab-url', 'https://gitlab.com',
                        '--token', 'abc123', '--group-ids', 'group1'])
    def test_parse_args_required_only(self):
        args = sbg.parse_args()
        self.assertEqual(args.gitlab_url, 'https://gitlab.com')
        self.assertEqual(args.token, 'abc123')
        self.assertEqual(args.group_ids, ['group1'])
        self.assertEqual(args.dest, '.')
        self.assertFalse(args.use_ssh)


class TestGitLabCloner(unittest.TestCase):
    def setUp(self):
        self.cloner = sbg.GitLabCloner('https://gitlab.com', 'token123', False)
        self.session_mock = MagicMock()
        self.cloner.session = self.session_mock

    def test_init(self):
        cloner = sbg.GitLabCloner('https://gitlab.com/', 'token123', True)
        self.assertEqual(cloner.base_url, 'https://gitlab.com/')
        self.assertEqual(cloner.session.headers.get('Private-Token'), 'token123')
        self.assertTrue(cloner.use_ssh)

    @patch('requests.Session')
    def test_get_single_page(self, session_mock):
        # Setup response mock for a single page
        response_mock = MagicMock()
        response_mock.json.return_value = [{'id': 1}, {'id': 2}]
        session_mock.return_value.get.return_value = response_mock

        cloner = sbg.GitLabCloner('https://gitlab.com', 'token123', False)
        result = cloner._get('/api/v4/groups/123/projects')

        self.assertEqual(result, [{'id': 1}, {'id': 2}])
        session_mock.return_value.get.assert_called_once()

    @patch('requests.Session')
    def test_get_pagination(self, session_mock):
        # Setup response mocks for pagination
        response1 = MagicMock()
        response1.json.return_value = [{'id': i} for i in range(100)]
        response2 = MagicMock()
        response2.json.return_value = [{'id': i} for i in range(100, 150)]
        response3 = MagicMock()
        response3.json.return_value = []

        session_mock.return_value.get.side_effect = [response1, response2, response3]

        cloner = sbg.GitLabCloner('https://gitlab.com', 'token123', False)
        result = cloner._get('/api/v4/groups/123/projects')

        self.assertEqual(len(result), 150)
        self.assertEqual(session_mock.return_value.get.call_count, 2)

    def test_list_subgroups(self):
        self.cloner._get = MagicMock(return_value=[{'id': 10}, {'id': 11}])
        result = self.cloner.list_subgroups(123)

        self.cloner._get.assert_called_once_with('/api/v4/groups/123/subgroups')
        self.assertEqual(result, [{'id': 10}, {'id': 11}])

    def test_list_projects(self):
        self.cloner._get = MagicMock(return_value=[{'id': 101}, {'id': 102}])
        result = self.cloner.list_projects(123)

        self.cloner._get.assert_called_once_with('/api/v4/groups/123/projects',
                                                 params={'include_subgroups': False})
        self.assertEqual(result, [{'id': 101}, {'id': 102}])

    def test_gather_all_projects(self):
        # Mock responses for different API calls
        def side_effect(path, params=None):
            if 'subgroups' in path:
                if '123' in path:
                    return [{'id': 456}, {'id': 789}]
                return []
            elif 'projects' in path:
                if '123' in path:
                    return [{'id': 1, 'name': 'Project1'}]
                elif '456' in path:
                    return [{'id': 2, 'name': 'Project2'}]
                elif '789' in path:
                    return [{'id': 3, 'name': 'Project3'}]
            return []

        self.cloner._get = MagicMock(side_effect=side_effect)
        result = self.cloner.gather_all_projects(123)

        # Should have 3 projects from main group and 2 subgroups
        self.assertEqual(len(result), 3)
        self.assertEqual({p['id'] for p in result}, {1, 2, 3})

    def test_gather_all_projects_with_http_error(self):
        # Test handling of HTTP errors for some groups
        def side_effect(path, params=None):
            if '123' in path:
                if 'subgroups' in path:
                    return [{'id': 456}, {'id': 789}]
                else:
                    return [{'id': 1, 'name': 'Project1'}]
            elif '456' in path:
                raise requests.HTTPError("Not found")
            elif '789' in path and 'projects' in path:
                return [{'id': 3, 'name': 'Project3'}]
            return []

        self.cloner._get = MagicMock(side_effect=side_effect)

        # Redirect stdout to capture warnings
        saved_stdout = sys.stdout
        try:
            out = StringIO()
            sys.stdout = out
            result = self.cloner.gather_all_projects(123)

            # Should have 2 projects and a warning
            self.assertEqual(len(result), 2)
            self.assertIn("Warning", out.getvalue())
        finally:
            sys.stdout = saved_stdout

    @patch('subprocess.check_call')
    @patch('os.path.isdir')
    def test_clone_new_repo(self, isdir_mock, subprocess_mock):
        # Mock that target directory doesn't exist
        isdir_mock.return_value = False

        sbg.GitLabCloner.clone_or_pull('https://gitlab.com/user/repo.git', '/tmp/repo')

        subprocess_mock.assert_called_once_with(['git', 'clone',
                                                 'https://gitlab.com/user/repo.git', '/tmp/repo'])

    @patch('subprocess.check_call')
    @patch('os.path.isdir')
    def test_pull_existing_repo(self, isdir_mock, subprocess_mock):
        # Mock that target directory exists and is a git repo
        isdir_mock.side_effect = lambda path: True

        sbg.GitLabCloner.clone_or_pull('https://gitlab.com/user/repo.git', '/tmp/repo')

        subprocess_mock.assert_called_once_with(['git', '-C', '/tmp/repo', 'pull'])

    @patch('subprocess.check_call')
    @patch('os.path.isdir')
    def test_clone_error_handling(self, isdir_mock, subprocess_mock):
        # Mock that target directory doesn't exist but clone fails
        isdir_mock.return_value = False
        subprocess_mock.side_effect = subprocess.CalledProcessError(1, 'git clone')

        # Redirect stdout to capture error message
        saved_stdout = sys.stdout
        try:
            out = StringIO()
            sys.stdout = out
            sbg.GitLabCloner.clone_or_pull('https://gitlab.com/user/repo.git', '/tmp/repo')
            self.assertIn("❌ clone failed", out.getvalue())
        finally:
            sys.stdout = saved_stdout


@patch('sbg.GitLabCloner')
@patch('os.makedirs')
@patch('os.path.abspath')
class TestMain(unittest.TestCase):
    def test_main_with_multiple_groups(self, abspath_mock, makedirs_mock, cloner_class_mock):
        # Setup mocks
        abspath_mock.return_value = '/absolute/path'

        cloner_instance = cloner_class_mock.return_value
        # Mock projects from two groups
        cloner_instance.gather_all_projects.side_effect = [
            [{'id': 1, 'path': 'project1', 'namespace': {'full_path': 'group1'},
              'http_url_to_repo': 'http://gitlab.com/group1/project1.git'}],
            [{'id': 2, 'path': 'project2', 'namespace': {'full_path': 'group2'},
              'http_url_to_repo': 'http://gitlab.com/group2/project2.git'}]
        ]

        # Setup and run main
        args = MagicMock()
        args.gitlab_url = 'https://gitlab.com'
        args.token = 'token123'
        args.group_ids = ['123', '456']
        args.dest = '/backup'
        args.use_ssh = False

        with patch('sbg.parse_args', return_value=args):
            with patch('sys.stdout', new=StringIO()):  # Suppress print statements
                sbg.main()

        # Verify
        self.assertEqual(cloner_instance.gather_all_projects.call_count, 2)
        self.assertEqual(makedirs_mock.call_count, 3)  # Root + 2 namespaces
        self.assertEqual(cloner_instance.clone_or_pull.call_count, 2)

    def test_main_with_path_with_namespace_fallback(self, abspath_mock, makedirs_mock, cloner_class_mock):
        # Test namespace fallback when namespace field is missing
        abspath_mock.return_value = '/absolute/path'

        cloner_instance = cloner_class_mock.return_value
        # Project with path_with_namespace but no namespace field
        cloner_instance.gather_all_projects.return_value = [
            {'id': 1, 'path': 'project1',
             'path_with_namespace': 'group1/subgroup/project1',
             'http_url_to_repo': 'http://gitlab.com/group1/subgroup/project1.git'}
        ]

        # Setup and run main
        args = MagicMock()
        args.gitlab_url = 'https://gitlab.com'
        args.token = 'token123'
        args.group_ids = ['123']
        args.dest = '/backup'
        args.use_ssh = False

        with patch('sbg.parse_args', return_value=args):
            with patch('sys.stdout', new=StringIO()):  # Suppress print statements
                sbg.main()

        # Verify namespace is properly extracted from path_with_namespace
        expected_parent = '/absolute/path/group1/subgroup'
        makedirs_mock.assert_any_call(expected_parent, exist_ok=True)

    def test_main_with_ssh_urls(self, abspath_mock, makedirs_mock, cloner_class_mock):
        # Test that SSH URLs are used when use_ssh is True
        abspath_mock.return_value = '/absolute/path'

        cloner_instance = cloner_class_mock.return_value
        cloner_instance.gather_all_projects.return_value = [
            {'id': 1, 'path': 'project1', 'namespace': {'full_path': 'group1'},
             'http_url_to_repo': 'http://gitlab.com/group1/project1.git',
             'ssh_url_to_repo': 'git@gitlab.com:group1/project1.git'}
        ]

        # Setup and run main with use_ssh=True
        args = MagicMock()
        args.gitlab_url = 'https://gitlab.com'
        args.token = 'token123'
        args.group_ids = ['123']
        args.dest = '/backup'
        args.use_ssh = True

        with patch('sbg.parse_args', return_value=args):
            with patch('sys.stdout', new=StringIO()):
                sbg.main()

        # Verify SSH URL is used
        cloner_instance.clone_or_pull.assert_called_with(
            'git@gitlab.com:group1/project1.git',
            '/absolute/path/group1/project1'
        )


if __name__ == '__main__':
    unittest.main()
