import subprocess
import apprise
import sys
import time
import yaml
import traceback
from mergedeep import merge


configuration = dict()
current_metric = dict()
notify_timer = dict()
notification_bot = apprise.Apprise()


def notify(notify_header: str, notify_body: str):
    with apprise.LogCapture() as capture:
        if not notification_bot.notify(body=notify_body, title=notify_header):
            print(capture.getvalue())
            notification_bot.notify(
                title = "!!!Critical!!!\n" + \
                    "Apprise cant send notification with following error:\n",
                body = capture.getvalue()
            )
            

def filter_status(stdout: str, stderr: str):
    if stderr != '':
        notify_header = "!!!Critical!!!\n" + \
            "Host - " + current_metric["host"] + "\n" \
            "The next error was obtained during the monitoring process:\n"
        notify_body = stderr
        return notify_header, notify_body
        

    for filter in current_metric["filters"]:
        action = filter[0:1]
        filter = filter[1:]
        stdout = stdout.strip("\n")
        stdout = stdout.strip("\t")

        notify_header = current_metric["notify"]["header"]
        notify_body = current_metric["notify"]["body"]
        if action == "=" and stdout != filter:
            return notify_header, notify_body
        if action == "!" and stdout == filter:
            return notify_header, notify_body
        if action == ">" and float(stdout) >= float(filter):
            return notify_header, notify_body
        if action == "<" and float(stdout) <= float(filter):
            return notify_header, notify_body
        return None, None


def run_ssh_command(command: str) -> str:
    ssh = "ssh " 
    if "key" in current_metric:
        ssh += "-i " + current_metric["key"] + " "
    ssh += current_metric["user"] + "@" + current_metric["host"]

    process = subprocess.Popen(str(ssh  + " " + command).split(),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output = process.communicate()
    return [output[0].decode("utf-8"), output[1].decode("utf-8")]


def set_timer():
    for label in configuration["metrics"]:
        notify_timer[label] = configuration["metrics"][label]["notify_every"]


def process_args(args: list):
    if "--config" not in args:
            raise Exception('Config file not provided!')
    for index, value in enumerate(args):
        if value == "-s":
            configuration["sleep"] = args.pop(index + 1)
        elif value == "--config":
            config = open(args.pop(index + 1), "r")
            config = yaml.safe_load(config)
            merge(configuration, config)
        else:
            raise Exception('Unknown argument: ' + value)


def main():
    process_args(sys.argv[1:])
    set_timer()

    global configuration 
    global current_metric 
    global notify_timer 

    notification_bot.add('tgram://' + configuration["bot_api"] + '/' + configuration["chat_id"] + '/')

    while True:
        for label in configuration["metrics"]:
            current_metric = configuration["metrics"][label]
            command_output = run_ssh_command(current_metric["command"])
            filter_result = filter_status(stdout=command_output[0], stderr=command_output[1])

            if filter_result[0] is not None and notify_timer[label] <= 0:
                notify(filter_result[0], filter_result[1])

            if notify_timer[label] <= 0:
                notify_timer[label] = current_metric["notify_every"]
            else:
                notify_timer[label] -= configuration["sleep"]


        time.sleep(configuration["sleep"])


if __name__ == '__main__':
    try:
        main()
    except Exception as err:
        traceback.print_exc()
        notify(
            notify_header = "!!!Critical!!!\n" + \
                "Alert service is a down\n" + \
                "The service has broken due to the next error:",
            notify_body = traceback.format_exc().replace("<", "").replace(">", "")
        )
        exit
