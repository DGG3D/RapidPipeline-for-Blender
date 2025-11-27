import sys
import os
import http.client
from typing import Tuple
import json

from .utils import saveJSON, loadJSON

class ProcessorLicense:
    # defines user folder for the plugin
    if 'darwin' in sys.platform:
        USER_FOLDER : str = os.path.join(os.path.expanduser("~"), 'Documents')
    else:
        USER_FOLDER : str = os.getenv("LOCALAPPDATA")
    PLUGIN_USER_FOLDER : str = os.path.join(USER_FOLDER, "RapidPipeline 3D Processor Plugins")
    LICENSE_FILE : str = os.path.join(PLUGIN_USER_FOLDER, "rpd_account.json")
    TEMP_LICENSE_FILE : str = os.path.join(PLUGIN_USER_FOLDER, "temp_rpd_account.json")

    @staticmethod
    def hasLicense() -> bool:
        # if the plugin has its own license file, use it
        if os.path.isfile(ProcessorLicense.LICENSE_FILE):
            # sets envvar for the plugin License File
            os.environ["RPD_ACCOUNTFILE"] = ProcessorLicense.LICENSE_FILE
            return True

        # if there's no license file for the plugin, see global envvar
        if "RPD_ACCOUNTFILE" in os.environ and os.path.isfile(os.environ["RPD_ACCOUNTFILE"]):
            return True
        return False

    @staticmethod
    def getAPIToken() -> str:
        if not os.environ.get("RPD_ACCOUNTFILE", ""):
            return ""
        return loadJSON(os.environ["RPD_ACCOUNTFILE"]).get("token", "")

    @staticmethod
    def createLicenseFile(token: str, is_temp: bool, update_env:bool = False) -> str:
        if is_temp:
            file_path = ProcessorLicense.TEMP_LICENSE_FILE
        else:
            file_path = ProcessorLicense.LICENSE_FILE

        account_data = {"host": "api.rapidpipeline.com", "token": token}

        print(f"Creating account file: {file_path}...")
        if not saveJSON(account_data, file_path):
            return None

        if update_env:
            os.environ["RPD_ACCOUNTFILE"] = file_path

        return file_path

    @staticmethod
    def getUserInformation() -> Tuple[int, dict]:
        api_token = ProcessorLicense.getAPIToken()
        if not api_token:
            return None

        conn = http.client.HTTPSConnection("api.rapidpipeline.com")
        payload = ''
        headers = {
        'Accept': 'application/json',
        'Authorization': f'Bearer {api_token}'
        }
        conn.request("GET", "/api/v2/user", payload, headers)
        res = conn.getresponse()
        return res.getcode(), json.loads(res.read().decode("utf-8"))

    @staticmethod
    def isTokenValid() -> bool:
        code, info = ProcessorLicense.getUserInformation()
        if code != 200:
            print(f'{info.get("message")} - {info.get("error")}')
            return False
        return True

    @staticmethod
    def getUserEmail() -> str:
        code, info = ProcessorLicense.getUserInformation()
        if code != 200:
            print(f'{info.get("message")} - {info.get("error")}')
            return ""
        return info.get("data", {}).get("email", "")
