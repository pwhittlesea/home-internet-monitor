import argparse
import json
import logging
import subprocess
import sys

from influxdb import InfluxDBClient

LOGGER = None


def set_up_logging():
    global LOGGER
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    root.addHandler(handler)
    LOGGER = logging.getLogger("speedtest")


def ensure_db_exists(client, db_name):
    dbs = client.get_list_database()
    for db in dbs:
        if db["name"] == db_name:
            LOGGER.debug("Skipping creation of DB with name '%s'", db_name)
            return

    LOGGER.warn("Creating Influx DB with name '%s'", db_name)
    client.create_database(db_name)
    client.alter_retention_policy(database=db_name, duration="7 days")


def speedtest(client):
    cmd = "/usr/bin/speedtest --format=json"
    try:
        response = (
            subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
            .stdout.read()
            .decode("utf-8")
        )
        response_dict = json.loads(response)
        fields = {
            "download": float(response_dict["download"]["bandwidth"]),
            "upload": float(response_dict["upload"]["bandwidth"]),
            "ping": float(response_dict["ping"]["latency"]),
            "jitter": float(response_dict["ping"]["jitter"]),
            "packet_loss": float(response_dict["packetLoss"]),
        }
        client.write_points(
            [
                {
                    "measurement": "internet_speed",
                    "tags": {
                        "host": "speed_test_2",
                        "server": response_dict["server"]["name"],
                        "location": response_dict["server"]["location"],
                    },
                    "fields": fields,
                }
            ]
        )
    except Exception as e:
        LOGGER.error("Error while running speedtest", exc_info=e)


def main():
    default_influx_host = "localhost"
    default_influx_port = 8086
    default_influx_db_name = "internetspeed"
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "influx-user", type=str, help="The username of the Influx DB user"
    )
    parser.add_argument(
        "influx-pass", type=str, help="The password of the Influx DB user"
    )

    parser.add_argument(
        "--influx-host",
        type=str,
        default=default_influx_host,
        help="The Influx DB host",
    )
    parser.add_argument(
        "--influx-port",
        type=int,
        default=default_influx_port,
        help="The Influx DB port",
    )
    parser.add_argument(
        "--influx-db",
        type=str,
        default=default_influx_db_name,
        help="The Influx DB database name",
    )

    args = vars(parser.parse_args())

    # Set up the logging framework for this application
    set_up_logging()

    # Create a new Influx Client
    client = InfluxDBClient(
        host=args["influx_host"],
        port=args["influx_port"],
        database=args["influx_db"],
        username=args["influx-user"],
        password=args["influx-pass"],
    )

    # Set the database up
    ensure_db_exists(client, args["influx_db"])

    # Run a speed test and run it on the database
    speedtest(client)


if __name__ == "__main__":
    main()
