import json
import requests

from chain.dfuse import DfuseConnection, ResponseError, Response, ResponseSuccessful
from constants import atomic_assets_account, dfuse_api_key
from database import Database
from log.log import Log


class ResponseException(Exception):
    pass


LOG = Log(className="AtomicAssetsData")


class AtomicAssetsData:
    dfuseConnection: DfuseConnection

    def __init__(self, dfuseApiKey: str, database: Database):
        LOG.info("Initialization of EdenChain")
        assert isinstance(dfuseApiKey, str), "dfuseApiKey must be type of str"
        assert isinstance(database, Database), "database must be type of Database"
        self.dfuseConnection = DfuseConnection(dfuseApiKey=dfuseApiKey, database=database)

    def getAssetsTemplateID(self, accountName: str, height: int = None) -> Response:
        try:
            LOG.info("Get assets 'template_id' state on height: " + str(height) if height is not None else "<current/live>")
            assert accountName is not None
            ACCOUNT = atomic_assets_account
            TABLE = 'assets'
            #PRIMARY_KEY = 'elect.state'
            SCOPE = accountName

            data =  self.dfuseConnection.getTable(account=ACCOUNT,
                                                    table=TABLE,
                                                    scope=SCOPE,
                                                    height=height)

            return data
        except Exception as e:
            LOG.exception(str(e))
            return ResponseError("Exception thrown when called getElectionState; Description: " + str(e))


    def getTemplateID(self, templateID: str, height: int = None) -> Response:
        try:
            LOG.info("Get template 'template_id' state on height: " + str(height) if height is not None else "<current/live>")
            assert templateID is not None
            ACCOUNT = atomic_assets_account
            TABLE = 'templates'
            #PRIMARY_KEY = 'elect.state'
            SCOPE = 'genesis.eden'

            data = self.dfuseConnection.getTable(account=ACCOUNT,
                                                    table=TABLE,
                                                    scope=SCOPE,
                                                    height=height)

            return data
        except Exception as e:
            LOG.exception(str(e))
            return ResponseError("Exception thrown when called getElectionState; Description: " + str(e))

    def getTGfromTemplateID(self, templateID: int,  height: int = None) -> Response:
        try:
            LOG.info("Get telegram ID from template id on height: " + str(templateID) if height is not None else "<current/live>")

            COLLECTION_NAME = 'genesis.eden'
            url = requests.get("https://eos.api.atomicassets.io/atomicassets/v1/templates/" + COLLECTION_NAME + "/" + str(templateID))
            #url = requests.get("https://jungle-aa.edenia.cloud/atomicassets/v1/templates/" + COLLECTION_NAME + "/" + str(templateID))

            if url.status_code == 200:
                jsonData = json.loads(url.text)
                if jsonData['success']:
                    social = jsonData['data']['immutable_data']['social']
                    socialJson = json.loads(social)
                    if 'telegram' in socialJson:
                        return ResponseSuccessful(socialJson['telegram'])
                    else:
                        return ResponseError("No telegram in social data")
            #otherwise return error
            return ResponseError("Error when getting participant data")


        except Exception as e:
            LOG.exception(str(e))
            return ResponseError("Exception thrown when called getElectionState; Description: " + str(e))

    def getParticipantTG(self, asset_id: str,  height: int = None) -> Response:
        try:
            #must be asset not template id
            LOG.info("Get participant telegram ID on height: " + str(height) if height is not None else "<current/live>")


            url = requests.get("https://eos.api.atomicassets.io/atomicmarket/v1/assets/" + asset_id)

            if url.status_code == 200:
                jsonData = json.loads(url.text)
                if jsonData['success']:
                    social = jsonData['data']['data']['social']
                    socialJson = json.loads(social)
                    if 'telegram' in socialJson:
                        return ResponseSuccessful(socialJson['telegram'])
                    else:
                        return ResponseError("No telegram in social data")
            #otherwise return error
            return ResponseError("Error when getting participant data")


        except Exception as e:
            LOG.exception(str(e))
            return ResponseError("Exception thrown when called getElectionState; Description: " + str(e))


    def getTGNameOfUser(self, accountName: str):
        '''atomicassets -> table assets(accounid) -> poglej template id
        table template (scope pomelo, pravilen genesis.eden) poisci
        posamezni template id.-> serialized_data'''
        try:
            #TODO: not working
            LOG.info("Get TG name of user")
            tmps = self.getAssetsTemplateID(accountName=accountName)

            if tmps.successful is True:
                wer = tmps.data
                for key, value in tmps.data.items():
                    print("Assets row: " + str(value))
                    if (len(value) > 0 and
                            value['collection_name'] is not None and
                            value['collection_name'] == "genesis.eden"):
                        print("Found collection name")
                        return self.getParticipantTG(asset_id=value['asset_id'])
            raise ResponseException("No participant data found")
        except Exception as e:
            LOG.exception(str(e))
            return ResponseError("Exception when getting TG name of user: " + str(e))




def main():
    print("Hello World!")
     #database = Database(databaseName="a", password="", port=50, host="", user="")
    dfuseObj = AtomicAssetsData(dfuseApiKey=dfuse_api_key)
    kva = dfuseObj.getTGNameOfUser(accountName='lukaperrrcic')
    kva1 = dfuseObj.getParticipantTG(asset_id='1406')
    kva2 = dfuseObj.getTGfromTemplateID(templateID=1406)

    ret = 9


if __name__ == "__main__":
    main()
