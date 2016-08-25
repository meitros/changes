from __future__ import absolute_import

import mock
import os

from flask import current_app

from changes.buildsteps.default import DEFAULT_PATH
from changes.models.command import CommandType
from changes.models.jobplan import JobPlan
from changes.testutils import TestCase


class AutogeneratedJobTest(TestCase):
    @mock.patch('changes.models.project.Project.get_config')
    def test_autogenerated_commands(self, get_config):
        get_config.return_value = {
            'bazel.targets': [
                '//aa/bb/cc/...',
                '//aa/abc/...',
            ],
            'bazel.dependencies': {
                'encap': [
                    'package1',
                    'pkg-2',
                ]
            }
        }

        current_app.config['APT_SPEC'] = 'deb http://example.com/debian distribution component1'
        current_app.config['ENCAP_RSYNC_URL'] = 'rsync://example.com/encap/'
        current_app.config['BAZEL_APT_PKGS'] = ['bazel']

        project = self.create_project()
        plan = self.create_plan(project)
        option = self.create_option(
            item_id=plan.id,
            name='bazel.autogenerate',
            value='1',
        )
        build = self.create_build(project)
        job = self.create_job(build)
        jobplan = self.create_job_plan(job, plan)

        _, implementation = JobPlan.get_build_step_for_job(job.id)

        bazel_setup_expected = """#!/bin/bash -eux
# Clean up any existing apt sources
sudo rm -rf /etc/apt/sources.list.d
# Overwrite apt sources
echo "deb http://example.com/debian distribution component1" | sudo tee /etc/apt/sources.list

# apt-get update, and try again if it fails first time
sudo apt-get -y update || sudo apt-get -y update
sudo apt-get install -y --force-yes bazel
""".strip()

        sync_encap_expected = """
sudo mkdir -p /usr/local/encap/
sudo /usr/bin/rsync -a --delete rsync://example.com/encap/package1 /usr/local/encap/
sudo /usr/bin/rsync -a --delete rsync://example.com/encap/pkg-2 /usr/local/encap/
""".strip()

        collect_tests_expected = """#!/bin/bash -eu
# Clean up any existing apt sources
sudo rm -rf /etc/apt/sources.list.d >/dev/null 2>&1
# Overwrite apt sources
(echo "deb http://example.com/debian distribution component1" | sudo tee /etc/apt/sources.list) >/dev/null 2>&1

# apt-get update, and try again if it fails first time
(sudo apt-get -y update || sudo apt-get -y update) >/dev/null 2>&1
sudo apt-get install -y --force-yes bazel python >/dev/null 2>&1

(/usr/bin/bazel --nomaster_blazerc --blazerc=/dev/null --batch query 'tests(//aa/bb/cc/... + //aa/abc/...)' | python -c "import sys
import json


targets = sys.stdin.read().splitlines()
out = {
    'cmd': '/usr/bin/bazel test {test_names}',
    'tests': targets,
}
json.dump(out, sys.stdout)
") 2> /dev/null
""".strip()

        assert len(implementation.commands) == 3

        assert implementation.commands[0].type == CommandType.setup
        assert implementation.commands[0].script == bazel_setup_expected

        assert implementation.commands[1].type == CommandType.setup
        assert implementation.commands[1].script == sync_encap_expected

        assert implementation.commands[2].type == CommandType.collect_tests
        assert implementation.commands[2].script == collect_tests_expected

        assert implementation.artifact_search_path == os.path.join(DEFAULT_PATH, current_app.config['BAZEL_TEST_OUTPUT_RELATIVE_PATH'])
        assert implementation.artifacts == ['*.xml']
