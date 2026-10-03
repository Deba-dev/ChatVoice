PHASE = 4
VERSION = "0.4.0"       # the number the updater compares (keep it in step with installer.iss and version_info.txt)
STAGE = "BETA"
CREATOR = "itsmeblitz"


def label():
    return "Phase %d \u00b7 v%s (%s)" % (PHASE, VERSION, STAGE)
