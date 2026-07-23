import os
import sys
import time
import subprocess
import oracledb # type: ignore

from datetime import datetime
from backend import submit_trade
from backend import search_trade


TARGET_ENV = os.getenv(
    "TARGET_ENV",
    "Smoke3"
)

ENVIRONMENTS = {

    "Smoke2": {

        "display_name": "Smoke 2",

        "backend_env": "Smoke2",

        "ssh_user": "smoke2",

        "host":
            "otc-clearing-test-smoke2-primary-rhel-01."
            "clearing-otc.dev.gcp.dbgcloud.io"
    },

    "Smoke3": {

        "display_name": "Smoke 3",

        "backend_env": "Smoke3",

        "ssh_user": "smoke3",

        "host":
            "otc-clearing-test-smoke3-primary-rhel-01."
            "clearing-otc.dev.gcp.dbgcloud.io"
    }
}

ENV_CONFIG = ENVIRONMENTS[TARGET_ENV]

ENVIRONMENT_NAME = ENV_CONFIG["display_name"]

TEMPLATE_XML = "trade.xml"

VALID_STATUSES = [
    "BS_FINALIZED",
    "VERIFIED"
]

ENV_READINESS_QUERY = """
SELECT TASK_ID,
       PARENT_ID,
       EXEC_STATUS,
       VAL_TIME
FROM quartz_sched_task_exec
WHERE task_id = '33584'
  AND parent_id = '19261'
  AND exec_status = 'success'
  AND TRUNC(val_time) = TRUNC(SYSDATE)
ORDER BY val_time DESC
"""


def create_email_summary(
    environment,
    status,
    reference="N/A",
    trade_id="N/A",
    trade_status="N/A",
    reason=""
):

    with open(
        "email_summary.txt",
        "w",
        encoding="utf-8"
    ) as f:

        f.write(
            "Environment Readiness Update\n\n"
        )

        f.write(
            f"Environment : {environment}\n"
        )

        f.write(
            f"Status      : {status}\n"
        )

        f.write(
            f"Reference   : {reference}\n"
        )

        f.write(
            f"Trade ID    : {trade_id}\n"
        )

        f.write(
            f"Trade Status: {trade_status}\n"
        )

        if reason:

            f.write(
                f"Reason      : {reason}\n"
            )


def check_environment_readiness():

    connection = None
    cursor = None

    try:

        connection = oracledb.connect(
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            dsn=os.getenv("DB_URL")
        )

        print("DB Connected")

        cursor = connection.cursor()

        cursor.execute(
            ENV_READINESS_QUERY
        )

        env_readiness_record = cursor.fetchone()

        if env_readiness_record:

            exec_status = env_readiness_record[2]
            val_time = env_readiness_record[3]

            print(
                "\nEnvironment Readiness Check PASSED"
            )

            print(
                f"Execution      : {exec_status}"
            )

            print(
                f"Execution Time : {val_time}"
            )

            return True

        print(
            "\nEnvironment Readiness Check FAILED"
        )

        return False

    except Exception as e:

        print(
            f"\nDatabase Error : {e}"
        )

        return False

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()

        print(
            "DB Disconnected"
        )


def get_next_internal_reference():

    return datetime.now().strftime(
        "%Y%m%d_SKP_%H%M%S_%f"
    )


def run_quartz_task():

    try:

        command = (
            f"ssh "
            f"{ENV_CONFIG['ssh_user']}@"
            f"{ENV_CONFIG['host']} "
            f"\"sh /home/"
            f"{ENV_CONFIG['ssh_user']}"
            f"/management-script/"
            f"executeTask.sh 19190\""
        )

        print(
            "\n===== TASK 19190 EXECUTION ====="
        )

        print(
            "\nExecuting Command:"
        )

        print(command)

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True
        )

        if result.stdout:
            print(result.stdout)

        if result.stderr:
            print(result.stderr)

        if result.returncode != 0:

            print(
                "\nTask 19190 execution failed"
            )

            return False

        print(
            "\nTask 19190 completed successfully"
        )

        return True

    except Exception as e:

        print(
            f"\nTask execution failed : {e}"
        )

        return False


def generate_trade_xml():

    try:

        timestamp = (
            datetime.now().strftime(
                "%Y-%m-%dT%H:%M:%S"
            )
        )

        trade_date = (
            datetime.now().strftime(
                "%Y-%m-%d"
            )
        )

        internal_reference = (
            get_next_internal_reference()
        )

        with open(
            TEMPLATE_XML,
            "r",
            encoding="utf-8"
        ) as f:

            xml_content = f.read()

        xml_content = xml_content.replace(
            "{{TIMESTAMP}}",
            timestamp
        )

        xml_content = xml_content.replace(
            "{{TRADE_DATE}}",
            trade_date
        )

        xml_content = xml_content.replace(
            "{{INTERNAL_REFERENCE}}",
            internal_reference
        )

        output_xml = (
            f"generated_trade_{internal_reference}.xml"
        )

        with open(
            output_xml,
            "w",
            encoding="utf-8"
        ) as f:

            f.write(xml_content)

        print(
            "\nTrade XML Generated"
        )

        print(
            f"Generated File : {output_xml}"
        )

        print(
            f"Reference      : {internal_reference}"
        )

        return (
            internal_reference,
            output_xml
        )

    except Exception as e:

        print(
            f"\nXML Generation Error : {e}"
        )

        return None, None


if __name__ == "__main__":

    print(
        "\n========================================"
    )

    print(
        "ENVIRONMENT READINESS NOTIFICATION"
    )

    print(
        "========================================"
    )

    print(
        f"Environment : {ENVIRONMENT_NAME}"
    )

    print(
        f"Execution   : {datetime.now()}"
    )

    env_ready = (
        check_environment_readiness()
    )

    if not env_ready:

        create_email_summary(
            ENVIRONMENT_NAME,
            "NOT READY",
            reason="Environment readiness check failed"
        )

        print(
            "\nSTATUS : NOT READY"
        )

        sys.exit(1)

    print(
        "\nSTATUS : READY"
    )

    internal_reference, output_xml = (
        generate_trade_xml()
    )

    if not internal_reference:

        create_email_summary(
            ENVIRONMENT_NAME,
            "FAILED",
            reason="Trade XML generation failed"
        )

        sys.exit(1)

    with open(
        output_xml,
        "r",
        encoding="utf-8"
    ) as f:

        xml_content = f.read()

    result = submit_trade(
        ENV_CONFIG["backend_env"],
        xml_content
    )

    print(
        "\n===== TRADE SUBMISSION ====="
    )

    print(result)

    if result["status"] != "SUCCESS":

        create_email_summary(
            ENVIRONMENT_NAME,
            "FAILED",
            reference=internal_reference,
            reason="Trade submission failed"
        )

        sys.exit(1)

    print(
        "\nTrade submitted successfully"
    )

    print(
        "\nWaiting 20 seconds for trade creation..."
    )

    time.sleep(20)

    quartz_success = (
        run_quartz_task()
    )

    if not quartz_success:

        create_email_summary(
            ENVIRONMENT_NAME,
            "FAILED",
            reference=internal_reference,
            reason="Task 19190 execution failed"
        )

        sys.exit(1)

    print(
        "\nWaiting 20 seconds after Task 19190..."
    )

    time.sleep(20)

    search_result = search_trade(
        ENV_CONFIG["backend_env"],
        internal_reference
    )

    print(
        "\n===== TRADE SEARCH ====="
    )

    if search_result["count"] == 0:

        create_email_summary(
            ENVIRONMENT_NAME,
            "FAILED",
            reference=internal_reference,
            reason="Trade not found"
        )

        sys.exit(1)

    trade = search_result["rows"][0]

    trade_status = trade["Status"]

    print(
        f"\nTrade ID      : {trade['Trade ID']}"
    )

    print(
        f"Reference     : {trade['External Reference']}"
    )

    print(
        f"Status        : {trade_status}"
    )

    if trade_status not in VALID_STATUSES:

        create_email_summary(
            ENVIRONMENT_NAME,
            "FAILED",
            reference=internal_reference,
            trade_id=trade["Trade ID"],
            trade_status=trade_status,
            reason=(
                "Trade not in an accepted status "
                "(BS_FINALIZED or VERIFIED)"
            )
        )

        sys.exit(1)

    create_email_summary(
        ENVIRONMENT_NAME,
        "READY",
        reference=internal_reference,
        trade_id=trade["Trade ID"],
        trade_status=trade_status
    )

    print(
        f"\nTrade reached accepted status: {trade_status}"
    )

    print(
        "\nEND-TO-END FLOW COMPLETED SUCCESSFULLY"
    )

    print(
        f"TRADE_ID={trade['Trade ID']}"
    )

    print(
        f"TRADE_STATUS={trade_status}"
    )

    print(
        f"REFERENCE={internal_reference}"
    )

    print(
        f"ENVIRONMENT={ENVIRONMENT_NAME}"
    )

    with open(
        "email.properties",
        "w",
        encoding="utf-8"
    ) as f:

        f.write(
            f"TRADE_ID={trade['Trade ID']}\n"
        )

        f.write(
            f"TRADE_STATUS={trade_status}\n"
        )

        f.write(
            f"REFERENCE={internal_reference}\n"
        )

        f.write(
            f'ENVIRONMENT="{ENVIRONMENT_NAME}"\n'
        )