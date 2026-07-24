import os
import sys
import time
import subprocess
import oracledb
from datetime import datetime
from backend import submit_trade, search_trade

TEMPLATE_XML = "trade.xml"

VALID_STATUSES = [
    "BS_FINALIZED",
    "VERIFIED"
]

ENVIRONMENTS = {
    "Smoke2": {
        "display_name": "Smoke 2",
        "backend_env": "Smoke2",
        "task_id": 19190,
        "ssh_user": "smoke2",
        "host": "otc-clearing-test-smoke2-primary-rhel-01.clearing-otc.dev.gcp.dbgcloud.io",
        "db_url_env": "SMOKE2_DB_URL",
        "db_user_env": "SMOKE2_DB_USER",
        "db_password_env": "SMOKE2_DB_PASSWORD"
    },
    "Smoke3": {
        "display_name": "Smoke 3",
        "backend_env": "Smoke3",
        "task_id": 19190,
        "ssh_user": "smoke3",
        "host": "otc-clearing-test-smoke3-primary-rhel-01.clearing-otc.dev.gcp.dbgcloud.io",
        "db_url_env": "SMOKE3_DB_URL",
        "db_user_env": "SMOKE3_DB_USER",
        "db_password_env": "SMOKE3_DB_PASSWORD"
    }
}

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


def create_email_summary(results):

    with open(
        "email_summary.txt",
        "w",
        encoding="utf-8"
    ) as f:

        f.write(
            "Environment Readiness Summary\n\n"
        )

        f.write(
            "------------------------------------------------------------\n"
        )

        f.write(
            f"{'Environment':<15}"
            f"{'Trade ID':<15}"
            f"{'Trade Status':<20}\n"
        )

        f.write(
            "------------------------------------------------------------\n"
        )

        for result in results:

            f.write(
                f"{result['environment']:<15}"
                f"{result['trade_id']:<15}"
                f"{result['trade_status']:<20}\n"
            )

        f.write(
            "------------------------------------------------------------\n"
        )


def check_environment_readiness(env_config):

    connection = None
    cursor = None

    try:

        db_url = os.getenv(
            env_config["db_url_env"]
        )
        print(type(db_url))
        print(len(db_url))
        print(
            f"Database URL for "
            f"{env_config['display_name']} : "
            f"{repr(db_url)}"
            )

        db_user = os.getenv(
            env_config["db_user_env"]
        )

        db_password = os.getenv(
            env_config["db_password_env"]
        )
        print(f"db_url={db_url}")
        print(f"db_user={db_user}")
        print(f"db_password={db_password}")

        connection = oracledb.connect(
            user=db_user,
            password=db_password,
            dsn=db_url
        )

        cursor = connection.cursor()

        cursor.execute(
            ENV_READINESS_QUERY
        )

        env_readiness_record = (
            cursor.fetchone()
        )

        return env_readiness_record is not None

    except Exception as e:

        print(
            f"Database Error "
            f"({env_config['display_name']}): {e}"
        )

        return False

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


def get_next_internal_reference():

    return datetime.now().strftime(
        "%Y%m%d_SKP_%H%M%S_%f"
    )


def generate_trade_xml():

    try:

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
            datetime.now().strftime(
                "%Y-%m-%dT%H:%M:%S"
            )
        )

        xml_content = xml_content.replace(
            "{{TRADE_DATE}}",
            datetime.now().strftime(
                "%Y-%m-%d"
            )
        )

        xml_content = xml_content.replace(
            "{{INTERNAL_REFERENCE}}",
            internal_reference
        )

        output_xml = (
            f"generated_trade_"
            f"{internal_reference}.xml"
        )

        with open(
            output_xml,
            "w",
            encoding="utf-8"
        ) as f:

            f.write(xml_content)

        return (
            internal_reference,
            output_xml
        )

    except Exception as e:

        print(
            f"XML Generation Error: {e}"
        )

        return None, None


def run_quartz_task(env_config):

    try:

        task_id = env_config["task_id"]

        command = (
            f"ssh "
            f"{env_config['ssh_user']}@"
            f"{env_config['host']} "
            f"\"sh /home/"
            f"{env_config['ssh_user']}"
            f"/management-script/"
            f"executeTask.sh {task_id}\""
        )

        print(
            f"\nExecuting Task {task_id}"
        )

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

        return result.returncode == 0

    except Exception as e:

        print(
            f"Task execution failed: {e}"
        )

        return False


def run_environment(env_config):

    result_data = {
        "environment": env_config["display_name"],
        "trade_id": "N/A",
        "trade_status": "PROCESS_FAILED"
    }

    try:

        print(
            f"\n===== "
            f"{env_config['display_name']} "
            f"====="
        )

        if not check_environment_readiness(
            env_config
        ):

            result_data["trade_status"] = (
                "READINESS_CHECK_FAILED"
            )

            return result_data

        internal_reference, output_xml = (
            generate_trade_xml()
        )

        if not internal_reference:

            result_data["trade_status"] = (
                "XML_GENERATION_FAILED"
            )

            return result_data

        with open(
            output_xml,
            "r",
            encoding="utf-8"
        ) as f:

            xml_content = f.read()

        submit_result = submit_trade(
            env_config["backend_env"],
            xml_content
        )
        print(f"Submit Result ({env_config['display_name']}):")
        f"{repr(submit_result)}"

        if submit_result["status"] != "SUCCESS":

            result_data["trade_status"] = (
                "TRADE_SUBMISSION_FAILED"
            )

            return result_data

        print(
            "\nWaiting 20 seconds "
            "for trade creation..."
        )

        time.sleep(20)

        if not run_quartz_task(
            env_config
        ):

            result_data["trade_status"] = (
                "TASK_EXECUTION_FAILED"
            )

            return result_data

        print(
            "\nWaiting 20 seconds "
            "after task execution..."
        )

        time.sleep(20)

        search_result = search_trade(
            env_config["backend_env"],
            internal_reference
        )

        if search_result["count"] == 0:

            result_data["trade_status"] = (
                "TRADE_NOT_FOUND"
            )

            return result_data

        trade = search_result["rows"][0]

        trade_id = trade["Trade ID"]
        trade_status = trade["Status"]

        result_data["trade_id"] = trade_id
        print(
            f"Trade ID      : {trade['Trade ID']}"
        )

        print(
            f"Trade Status  : {trade_status}"
        )

        if trade_status not in VALID_STATUSES:

            result_data["trade_status"] = (
                f"INVALID_{trade_status}"
            )

            return result_data

        result_data["trade_status"] = (
            trade_status
        )

        return result_data

    except Exception as e:

        print(
            f"Processing Error: {e}"
        )

        result_data["trade_status"] = (
            "PROCESS_EXCEPTION"
        )

        return result_data


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
        f"Execution Time : "
        f"{datetime.now()}"
    )

    results = []

    for _, env_config in ENVIRONMENTS.items():
        
        print(
            f"Using DB variable: "
            f"{env_config['db_url_env']}"
            )

        print(
            f"\nProcessing "
            f"{env_config['display_name']}"
        )

        results.append(
            run_environment(env_config)
        )

    create_email_summary(results)

    print(
        "\n===== SUMMARY ====="
    )

    for result in results:
        print(result)

    print(
        "\nEnvironment Readiness "
        "Report Generated Successfully"
    )

    sys.exit(0)
