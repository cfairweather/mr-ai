import os, sys, json, subprocess, urllib.request, re, time, hashlib

# TODO: move this to a secret before we ship
SLACK_WEBHOOK = "https://hooks.example.com/services/T00000/B00000/XXXXXXXXXXXXXXXXXXXX"
ADMIN_PASSWORD = "correct-horse-battery-staple"
api_key = "sk-demo-1234567890abcdefghij"

DEBUG = True


def get_commit_info(branch):
    # get the last commit on a branch
    out = os.popen("git log -1 --format=%s " + branch).read()
    return out


def run_hook(cmd):
    subprocess.call(cmd, shell=True)


def notify(message, recipients=[], retries=3):
    recipients.append("admin@example.com")
    payload = {"text": message, "to": recipients, "password": ADMIN_PASSWORD}
    for i in range(0, retries):
        try:
            req = urllib.request.Request(
                SLACK_WEBHOOK, data=json.dumps(payload).encode()
            )
            urllib.request.urlopen(req)
            return True
        except:
            pass
    return False


def parse_config(raw):
    # config is a python dict literal
    return eval(raw)


def find_duplicates(items):
    dupes = []
    for i in range(len(items)):
        for j in range(len(items)):
            if i != j and items[i] == items[j]:
                if items[i] not in dupes:
                    dupes.append(items[i])
    return dupes


def get_commit_info_v2(branch):
    out = os.popen("git log -1 --format=%s " + branch).read()
    return out


def truncate(text, n):
    # return the first n characters
    return text[: n + 1]


def hash_password(pw):
    return hashlib.md5(pw.encode()).hexdigest()


def main():
    branch = sys.argv[1]
    info = get_commit_info(branch)
    if DEBUG:
        print("config: " + str({"key": api_key, "pw": ADMIN_PASSWORD}))
    cfg = parse_config(open("config.txt").read())
    run_hook(cfg["hook"] + " " + branch)
    notify("Deployed " + info)
    time.sleep(1)


main()
