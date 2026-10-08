import shlex
import os

READ_ONLY_COMMANDS = {
    "pwd",
    "ls",
    "whoami",
    "date",
    "uname",
    "df",
    "du",
    "free",
    "ps",
}

WRITE_COMMANDS = {
    "mkdir",
    "touch",
    "cp",
    "mv",
}

EXECUTE_COMMANDS = {
    "python",
    "python3",
    "bash",
    "sh",
}

DANGEROUS_COMMANDS = {
    "rm",
    "rmdir",
    "mkfs",
    "dd",
    "shutdown",
    "reboot",
    "chmod",
    "chown",
    "ip",
    "iptables",
    "ufw",
    "systemctl",
    "service",
    "umount",
    "mount",
    "fdisk",
    "parted",
    "mkswap",
    "swapon",
    "swapoff",
    "init",
    "telinit",
}

# Directories where destructive operations are NOT allowed
HOME_DIRECTORY = os.path.expanduser("~")
PLUTO_WORKSPACE = os.path.join(HOME_DIRECTORY, "Pluto")

RESTRICTED_DIRECTORIES = {
    "/etc",
    "/root",
    "/usr",
    "/bin",
    "/sbin",
    "/lib",
    "/lib32",
    "/lib64",
    "/boot",
    "/var",
    "/sys",
    "/proc",
    "/dev",
    "/mnt",
    "/media",
    "/opt",
    "/tmp",
}

PATH_COMMANDS = {
    "ls",
    "du",
    "df",
}


ALLOW = "allow"
CONFIRM = "confirm"
DENY = "deny"


def normalize_path(path):
    return os.path.abspath(os.path.expanduser(path))


def resolve_path(path):
    return os.path.realpath(normalize_path(path))


def is_restricted_path(path):
    resolved = resolve_path(path)

    for restricted in RESTRICTED_DIRECTORIES:
        restricted_path = resolve_path(restricted)

        try:
            if os.path.commonpath([resolved, restricted_path]) == restricted_path:
                return True
        except ValueError:
            return True

    return False


def extract_paths(arguments, program):
    if program not in PATH_COMMANDS:
        return []

    paths = []

    for argument in arguments[1:]:
        if not argument.startswith("-"):
            paths.append(argument)

    return paths

def is_inside_workspace(path):
    resolved = resolve_path(path)
    workspace = resolve_path(PLUTO_WORKSPACE)

    try:
        return os.path.commonpath([resolved, workspace]) == workspace
    except ValueError:
        return False

def check_path_permission(path):
    if is_restricted_path(path):
        return DENY

    if is_inside_workspace(path):
        return ALLOW

    return CONFIRM

def check_command_permission(command):

    try:
        arguments = shlex.split(command)
    except ValueError:
        return DENY

    if not arguments:
        return DENY

    program = os.path.basename(arguments[0])

    # Hard-denied commands
    if program in DANGEROUS_COMMANDS:
        return DENY

    # Commands that modify the filesystem require confirmation
    if program in WRITE_COMMANDS:
        return CONFIRM

    # Commands that can execute arbitrary code require confirmation
    if program in EXECUTE_COMMANDS:
        return CONFIRM

    # Unknown commands require confirmation
    if program not in READ_ONLY_COMMANDS:
        return CONFIRM

    # Read-only commands can automatically read Pluto's workspace.
    paths = extract_paths(arguments, program)

    for path in paths:
        path_permission = check_path_permission(path)

        if path_permission == DENY:
            return DENY

        if path_permission == CONFIRM:
            return CONFIRM

    return ALLOW

if __name__ == "__main__":

    tests = [
        "pwd",
        "ls",
        "ls ~/Pluto",
        "ls ~/Pluto/main.py",
        "ls ~/Documents",
        "ls /etc",
        "ls /etc/passwd",
        "rm ~/Pluto/test.txt",
        "git status",
        "python script.py",
        "",
        'echo "hello',
    ]

    for command in tests:
        print(f"{command!r} -> {check_command_permission(command)}")