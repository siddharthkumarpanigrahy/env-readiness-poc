#!/bin/bash
set -e

ssh smoke3@otc-clearing-test-smoke3-primary-rhel-01.clearing-otc.dev.gcp.dbgcloud.io \
"sh /home/smoke3/management-script/executeTask.sh 19190"