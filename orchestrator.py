import os
import sys
import re
import time
import oracledb
from datetime import datetime
from backend import submit_trade
from backend import search_trade

ENVIRONMENT_NAME = "Smoke 3"

TEMPLATE_XML = "trade.xml"

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

        cursor.execute(ENV_READINESS_QUERY)

        env_readiness_record = cursor.fetchone()

        if env_readiness_record:

            exec_status = env_readiness_record[2]
            val_time = env_readiness_record[3]

            print("\nEnvironment Readiness Check PASSED")
            print(f"Execution      : {exec_status}")
            print(f"Execution Time : {val_time}")

            return True

        print("\nEnvironment Readiness Check FAILED")
        return False

    except Exception as e:

        print(f"\nDatabase Error : {e}")
        return False

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()

        print("DB Disconnected")


def get_next_internal_reference():

    current_day = datetime.now().strftime("%Y%m%d")

    try:

        with open(
            TEMPLATE_XML,
            "r",
            encoding="utf-8"
        ) as f:

            content = f.read()

        match = re.search(
            r'[0-9]{8}[^0-9A-Za-z]*SKP[^0-9]*([0-9]+)',
            content
        )

        sequence = int(match.group(1)) if match else 0

        next_sequence = f"{sequence + 1:02d}"

        return f"{current_day}_SKP_{next_sequence}"

    except Exception:

        return f"{current_day}_SKP_01"

import subprocess

def run_quartz_task():

    try:

        command = (
            '$CALYPSO_CODE/client/bin/calypso '
            '@$CALYPSO_CODE/client/resources/jvmArgs17.txt '
            '-Djavax.net.ssl.trustStore=/home/$USER/build/calypso-code/client/resources/certificates/client.truststore '
            '-Djavax.net.ssl.trustStorePassword=calypso '
            'com.calypso.apps.startup.StartQuartzTaskRunner '
            '-env $USER '
            '-user calypso_user '
            '-task 19190 '
            '$LOG_DIR'
        )

        print("\n===== QUARTZ TASK EXECUTION =====")
        print(f"Command : {command}")

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True
        )

        print(result.stdout)

        if result.returncode != 0:

            print(result.stderr)

            return False

        print("\n? Quartz Task 19190 completed")

        return True

    except Exception as e:

        print(f"\n? Quartz execution failed : {e}")

        return False


def generate_trade_xml():

    try:

        timestamp = datetime.now().strftime(
            "%Y-%m-%dT%H:%M:%S"
        )

        trade_date = datetime.now().strftime(
            "%Y-%m-%d"
        )

        internal_reference = get_next_internal_reference()

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

        print("\n✅ Trade XML Generated")
        print(f"Generated File : {output_xml}")
        print(f"Reference      : {internal_reference}")

        return internal_reference, output_xml

    except Exception as e:

        print(f"\n❌ XML Generation Error : {e}")

        return None, None


if __name__ == "__main__":

    print("\n========================================")
    print("ENVIRONMENT READINESS NOTIFICATION")
    print("========================================")
    print(f"Environment : {ENVIRONMENT_NAME}")
    print(f"Execution   : {datetime.now()}")

    env_ready = check_environment_readiness()

    if env_ready:

    print("\nSTATUS : READY")

    quartz_success = run_quartz_task()

    if not quartz_success:

        print("\n? Quartz task execution failed")

        sys.exit(1)

    internal_reference, output_xml = generate_trade_xml()

        if not internal_reference:

            print("\nTrade XML generation failed")
            sys.exit(1)

        print("\nTrade XML generated successfully")

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

        print("\n===== TRADE SUBMISSION =====")
        print(result)

        if result["status"] != "SUCCESS":

            print("\n❌ Trade submission failed")
            sys.exit(1)

        print("\n✅ Trade submitted successfully")

        print("\nWaiting 20 seconds for trade creation...")

        time.sleep(20)

        search_result = search_trade(
            "Smoke3",
            internal_reference
        )

        print("\n===== TRADE SEARCH =====")

       if search_result["count"] > 0:

    trade = search_result["rows"][0]

    trade_status = trade["Status"]

    print("\n? Trade Found")

    print(
        f"Trade ID      : "
        f"{trade['Trade ID']}"
    )

    print(
        f"Reference     : "
        f"{trade['External Reference']}"
    )

    print(
        f"Status        : "
        f"{trade_status}"
    )

    if trade_status == "BS_FINALIZED":

        print(
            "\n? Trade successfully "
            "reached BS_FINALIZED"
        )

    else:

        print(
            f"\n? Trade status is "
            f"{trade_status} "
            f"instead of BS_FINALIZED"
        )

        sys.exit(1)
        else:

            print(
                f"\n⚠ No trade found for "
                f"{internal_reference}"
            )

    else:

        print("\nSTATUS : NOT READY")
        sys.exit(1)
