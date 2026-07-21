import os
import sys
import re
import time
import subprocess
import oracledb # type: ignore

from datetime import datetime
from backend import submit_trade
from backend import search_trade


ENVIRONMENT_NAME = "Smoke 3"

TEMPLATE_XML = "trade.xml"

CALYPSO_CODE = (
    "/home/otcci/jenkins-eclci/workspace/"
    "OTC/OTC-Core/Accenture_Jobs/"
    "ManagedJobs/Git-files-no-hist"
)

LOG_DIR = "/tmp"


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

    current_day = datetime.now().strftime(
        "%Y%m%d"
    )

    try:

        with open(
            TEMPLATE_XML,
            "r",
            encoding="utf-8"
        ) as f:

            content = f.read()

        match = re.search(
            r"[0-9]{8}[^0-9A-Za-z]*SKP[^0-9]*([0-9]+)",
            content
        )

        sequence = (
            int(match.group(1))
            if match
            else 0
        )

        next_sequence = (
            f"{sequence + 1:02d}"
        )

        return (
            f"{current_day}_SKP_{next_sequence}"
        )

    except Exception:

        return f"{current_day}_SKP_01"


def run_quartz_task():

    try:

        command = (
            f"sh {CALYPSO_CODE}/client/bin/calypso "
            f"@{CALYPSO_CODE}/client/resources/jvmArgs17.txt "
            "-Djavax.net.ssl.trustStore=/home/$USER/build/calypso-code/client/resources/certificates/client.truststore "
            "-Djavax.net.ssl.trustStorePassword=calypso "
            "com.calypso.apps.startup.StartQuartzTaskRunner "
            "-env $USER "
            "-user calypso_user "
            "-task 19190 "
            f"{LOG_DIR}"
        )

        print(
            "\n===== QUARTZ TASK EXECUTION ====="
        )

        print(
            "\nExecuting Quartz Command:"
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
            return False

        print(
            "\nQuartz Task 19190 completed"
        )

        return True

    except Exception as e:

        print(
            f"\nQuartz execution failed : {e}"
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

    quartz_success = (
        run_quartz_task()
    )

    if not quartz_success:

        create_email_summary(
            ENVIRONMENT_NAME,
            "FAILED",
            reason="Quartz Task 19190 execution failed"
        )

        sys.exit(1)

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
        "Smoke3",
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

    search_result = search_trade(
        "Smoke3",
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

    if trade_status != "BS_FINALIZED":

        create_email_summary(
            ENVIRONMENT_NAME,
            "FAILED",
            reference=internal_reference,
            trade_id=trade["Trade ID"],
            trade_status=trade_status,
            reason="Trade not in BS_FINALIZED status"
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
        "\nTrade successfully reached BS_FINALIZED"
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
with open("email.properties", "w") as f:
    f.write(f"TRADE_ID={trade['Trade ID']}\n")
    f.write(f"TRADE_STATUS={trade_status}\n")
    f.write(f"REFERENCE={internal_reference}\n")
    f.write(f"ENVIRONMENT={ENVIRONMENT_NAME}\n")