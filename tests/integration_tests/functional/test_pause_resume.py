# Copyright 2020 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Basic tests scenarios for snapshot save/restore."""
import host_tools.network as net_tools  # pylint: disable=import-error
import logging
from conftest import test_images_s3_bucket
import json
from pathlib import Path
import pytest
from framework.artifacts import ArtifactCollection
from framework.matrix import TestMatrix


def _test_pause_resume(context, microvm):
    logger = context['logger']

    with open(context['microvm'].local_path(), 'r') as f:
        machine_config = json.load(f)

    logger.info("Microvm: {} vCPU(s) {} MB. Kernel \"{}\" "
                ", disk \"{}\""
                .format(machine_config['vcpu_count'],
                        machine_config['mem_size_mib'],
                        context['kernel'].name(),
                        context['disk'].name()))

    tap, _, _ = microvm.ssh_network_config(context['network_config'], '1')

    # Pausing the microVM before being started is not allowed.
    response = microvm.vm.patch(state='Paused')
    assert microvm.api_session.is_status_bad_request(response.status_code)

    # Resuming the microVM before being started is also not allowed.
    response = microvm.vm.patch(state='Resumed')
    assert microvm.api_session.is_status_bad_request(response.status_code)

    microvm.start()

    ssh_connection = net_tools.SSHConnection(microvm.ssh_config)

    # Verify guest is active.
    exit_code, _, _ = ssh_connection.execute_command("ls")
    assert exit_code == 0

    # Pausing the microVM after it's been started is successful.
    response = microvm.vm.patch(state='Paused')
    assert microvm.api_session.is_status_no_content(response.status_code)

    # Verify guest is no longer active.
    exit_code, _, _ = ssh_connection.execute_command("ls")
    assert exit_code != 0

    # Pausing the microVM when it is already `Paused` is allowed
    # (microVM remains in `Paused` state).
    response = microvm.vm.patch(state='Paused')
    assert microvm.api_session.is_status_no_content(response.status_code)

    # Resuming the microVM is successful.
    response = microvm.vm.patch(state='Resumed')
    assert microvm.api_session.is_status_no_content(response.status_code)

    # Verify guest is active again.
    exit_code, _, _ = ssh_connection.execute_command("ls")
    assert exit_code == 0

    # Resuming the microVM when it is already `Resumed` is allowed
    # (microVM remains in the running state).
    response = microvm.vm.patch(state='Resumed')
    assert microvm.api_session.is_status_no_content(response.status_code)

    # Verify guest is still active.
    exit_code, _, _ = ssh_connection.execute_command("ls")
    assert exit_code == 0

    microvm.kill()
    del tap


@pytest.mark.skipif(
    platform.machine() != "x86_64",
    reason="Not supported yet."
)
def test_pause_resume(test_session_root_path,
                      network_config,
                      bin_cloner_path):
    """Test scenario: boot/pause/resume for all available configurations."""
    logger = logging.getLogger()
    # Currently, artifacts share the bucket with all other resources.
    artifacts = ArtifactCollection(test_images_s3_bucket())

    microvm_artifacts = artifacts.microvms()
    kernel_artifacts = artifacts.kernels()
    disk_artifacts = artifacts.disks()

    # Create a test matrix. Push logger and network as context variables.
    test_matrix = TestMatrix(context={
            'network_config': network_config,
            'logger': logger
        })

    # Configure the text matrix variables.
    test_matrix.microvms = microvm_artifacts
    test_matrix.kernels = kernel_artifacts
    test_matrix.disks = disk_artifacts

    test_matrix.run_test(_test_pause_resume,
                         test_session_root_path,
                         bin_cloner_path)