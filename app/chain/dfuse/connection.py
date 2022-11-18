import json
from datetime import date, timedelta, datetime
import time as t
from http.client import HTTPSConnection
import requests as requests
from abieos import EosAbiSerializer

from app.constants import dfuse_url, dfuse_api_key, eos_node_url
from app.database.database import Database as Database1

from app.log import Log
import http.client


class DfuseError(Exception):
    pass

class ResponseException(Exception):
    pass

LOG = Log(className="DfuseConnection")
LOG_RETRY = Log(className="Connection.retry")
LOG_RESPONSE = Log(className="Response")

class Response:
    def __init__(self, successful: bool):
        LOG_RESPONSE.debug("Response; valid: " + str(successful))
        self._successful = successful

    @property
    def successful(self):
        return self._successful

class ResponseSuccessful(Response):
    def __init__(self, data: []):
        super(ResponseSuccessful, self).__init__(successful=True)
        if data is None:
            LOG_RESPONSE.error("Data cannot not be null")
            raise ResponseError("ResponseSuccessful: Data cannot be null")
        self._data = data

    def isEmpty(self) -> bool:
        return len(self._data)

    @property
    def data(self) -> []:
        return self._data


class ResponseError(Response):
    def __init__(self, error: str):
        super(ResponseError, self).__init__(successful=False)
        if error is None or len(error) == 0:
            LOG_RESPONSE.error("Error description cannot not be null/empty")
            raise ResponseError("ResponseError: Error description cannot be null/empty")
        self._error = error

    @property
    def error(self) -> str:
        return self._error

class DfuseConnection:
    dfuseToken: str = None

    def __init__(self, dfuseApiKey: str):
        if len(dfuseApiKey) == 0:
            LOG.exception("API key is null")
            raise DfuseError("API key is null")
        self.apiKeyParam = dfuseApiKey
        #self.connect()

    def getTokenFromApiKey(self) -> ():
        # returns token and expiration date
        try:
            connection = http.client.HTTPSConnection("auth.eosnation.io")
            connection.request('POST',
                               '/v1/auth/issue',
                               json.dumps({"api_key": self.apiKeyParam}),
                               {'Content-type': 'application/json'})
            response = connection.getresponse()

            if response.status != 200:
                raise Exception(f" Status: {response.status} reason: {response.reason}")

            decodedResponse: str = response.read().decode()
            self.dfuseToken = json.loads(decodedResponse)['token']
            expiresAt = json.loads(decodedResponse)['expires_at']
            expiresAtDT = datetime.fromtimestamp(expiresAt)
            LOG.debug("Token expires at: " + str(expiresAtDT))
            LOG.success("Dfuse token successfully saved")
            connection.close()
            return (self.dfuseToken, expiresAtDT)
        except Exception as e:
            LOG.exception("Exception thrown when called getTokenFromApiKey; Description: " + str(e))

    def headers(self) -> {}:
        return {'Authorization': 'Bearer ' + self.dfuseToken}

    def url(self) ->str:
        if dfuse_url is None:
            LOG.exception("There is no valid 'dfuse_url' entry in constant")
            raise ConnectionError("There is no valid 'dfuse_url' entry in constant")
        return dfuse_url #from constants

    def link(self, path: str) -> str:
        if path is None:
            LOG.exception("There is no valid 'path'")
            raise ConnectionError("There is no valid 'path'")
        return "" + self.url() + path

    def linkNode(self, path: str) -> str:
        if eos_node_url is None:
            LOG.exception("There is no valid 'eos_node_url' entry in constant")
            raise ConnectionError("There is no valid 'eos_node_url' entry in constant")
        if path is None:
            LOG.exception("There is no valid 'path'")
            raise ConnectionError("There is no valid 'path'")
        return "" + eos_node_url + path

    def connect(self) -> ():
        # returns token and expiration date
        LOG.info("Start establishing connection on dfuse")
        return DfuseConnection.retry(lambda: self.getTokenFromApiKey(), limit=3)

    def getAbiFromChain(self, account: str, height: int) ->Response:
        try:
            path = '/v0/state/abi'
            LOG.info("Path: " + path)
            LOG.info("Get abi; account: " + account)

            parameters = dict({
                'account': account
            })
            # if height is set (we are looking in the history)
            if height is not None:
                parameters.update({"block_num": height})

            LOG.debug("Request.get on path:" + path)
            result = DfuseConnection.retry(lambda: requests.get(
                self.link(path=path),
                params=parameters,
                headers=self.headers(), verify=False))

            abiHex = json.loads(result.text)
            if result.status_code == 200:
                LOG.success("Status code:200")
                database = Database1()
                database.saveOrUpdateAbi(account, abiHex['abi'])
                return ResponseSuccessful(abiHex['abi'])
            else:
                LOG.error("Status code: " + str(result.status_code) + " Error: " + result.get("message") + " " +
                          json.dumps(result.get("details")))
                return ResponseError(error=abiHex.get("message") + " " + json.dumps(abiHex.get("details")))
        except Exception as e:
            LOG.exception(str(e))
            return ResponseError("Exception thrown when called getAbi; Description: " + str(e))

    def parseHexWithAbi(self, account: str, table: str, hex: str, height: int = None) -> dict:
        try:
            if account is None or len(account) == 0:
                raise DfuseError("parseHexWithAbi; Account name is not valid")
            if table is None or len(account) == 0:
                raise DfuseError("parseHexWithAbi; Table name is not valid")
            if hex is None or len(account) == 0:
                raise DfuseError("parseHexWithAbi; Hex value is not valid")

            abiHex = None
            database = Database1()
            abi = database.getABI(accountName=account)
            if (abi is not None):
                LOG.info("ABI exists for account: " + account)
                abiObj: hex = abi.contract
                if (len(abiObj) == 0):
                    raise ResponseException("Could not get ABi from db: " + abiObj.error)
                abiHex = abiObj#.decode('utf-8')
            else:
                abiResponse = self.getAbiFromChain(account=account, height=height)
                if not abiResponse.successful:
                    raise DfuseError("cannot get abi from chain. Error: " + abiResponse.error)
                else:
                    abiHex = abiResponse.data
            s = EosAbiSerializer()
            if not s.set_abi_from_hex(account, abiHex):
                raise DfuseError("Cannot load abi from hex")

            LOG.info("Start parsing the data from hex to json")
            tableName = s.get_type_for_table(account, table)
            return ResponseSuccessful(data=s.hex_to_json(account, tableName, hex))
        except Exception as e:
            LOG.exception(str(e))
            return ResponseError("Exception thrown when called getAbi; Description: " + str(e))

    def getTableRow(self, account: str, table: str, primaryKey: str, scope: str = None, height: int = None, dateTime: datetime = None):
        try:
            path = '/v0/state/table/row'
            LOG.info("Path: " + path)
            LOG.info("Get table rows; account: " + account +
                     ", table: " + table +
                     ", primary key: " + primaryKey +
                     ", scope: " + scope +
                     ", height: " + str(height) +
                     ", datetime: " + dateTime.isoformat() if dateTime is not None else None)

            # if scope is zero we need to manually parse binary data to json
            isJson = False if scope is None else True

            parameters= dict({
                'account': account,
                "table": table,
                "primary_key": primaryKey,
                "scope": scope if scope is not None else "",
                "json": str(isJson).lower() #do not parse on server, not working because of abi version (for now)
            })
            #if height is set (we are looking in the history)
            if height is not None:
                parameters.update({"block_num": height})

            LOG.debug("Request.get on path:" + path)
            result = DfuseConnection.retry(lambda: requests.get(
                self.link(path=path),
                params=parameters,
                headers=self.headers(), verify=False))
            j = json.loads(result.text)
            if result.status_code == 200:
                LOG.success("Status code:200")
                data = j.get('row').get('json') if isJson else j.get('row').get('hex')
                if isJson:
                    return ResponseSuccessful(data=[data])
                else:
                    return ResponseSuccessful(self.parseHexWithAbi(account=account, table=table, hex=data))
            else:
                LOG.error("Status code: " + str(result.status_code) + " Error: " + j.get("message") + " " +
                          json.dumps(j.get("details")))
                return ResponseError(j.get("message") + " " + json.dumps(j.get("details")))
        except Exception as e:
            LOG.exception(str(e))
            return ResponseError("Exception thrown when called getTableRows; Description: " + str(e))

    def getBlockHeightFromTimestamp(self, timestamp: datetime) -> Response:
        try:
            path = '/v0/block_id/by_time'
            LOG.info("Path: " + path)
            LOG.info("Get block height from timestamp: " + timestamp.isoformat())

            parameters = dict({
                'time': timestamp.isoformat(),
                'comparator': 'gte'
            })

            LOG.debug("Request.get on path:" + path)
            result = DfuseConnection.retry(lambda: requests.get(
                self.link(path=path),
                params=parameters,
                headers=self.headers(), verify=False))

            j = json.loads(result.text)
            if result.status_code == 200:
                LOG.success("Status code:200")
                return ResponseSuccessful(data=j.get('block').get('num'))
            else:
                LOG.error("Status code: " + str(result.status_code) + " Error: " + j.get("message") + " " +
                          json.dumps(j.get("details")))
                return ResponseError(j.get("message") + " " + json.dumps(j.get("details")))
        except Exception as e:
            LOG.exception(str(e))
            return ResponseError("Exception thrown when called getBlockHeightFromTimestamp; Description: " + str(e))


    def getTable(self, account: str, table: str, scope: str = None, height: int = None, dateTime: datetime = None):
        try:
            path = '/v0/state/table'
            LOG.info("Path: " + path)
            LOG.info("Get table rows; account: " + account +
                     ", table: " + table +
                     ", scope: " + scope +
                     ", height: " + str(height) +
                     ", datetime: " + dateTime.isoformat() if dateTime is not None else None)

            # if scope is zero we need to manually parse binary data to json
            isJson = False if scope is None else True

            parameters= dict({
                'account': account,
                "table": table,
                "scope": scope if scope is not None else "",
                "json": str(isJson).lower() #do not parse on server, not working because of abi version (for now)
            })
            #if height is set (we are looking in the history)
            if height is not None:
                parameters.update({"block_num": height})

            LOG.debug("Request.get on path:" + path)
            result = DfuseConnection.retry(lambda: requests.get(
                self.link(path=path),
                params=parameters,
                headers=self.headers(), verify=False))
            j = json.loads(result.text)
            if result.status_code == 200:
                LOG.success("Status code:200")
                data = dict() # j.get('rows').get('json') if isJson else j.get('row').get('hex')

                for row in j.get('rows'):
                    data[row.get('key')] = row.get('json') if isJson \
                        else \
                        self.parseHexWithAbi(account=account, table=table, hex=row.get('hex'))

                #if isJson:
                return ResponseSuccessful(data)
                #else:
                #    return ResponseSuccessful(self.parseHexWithAbi(account=account, table=table, hex=data))
            else:
                LOG.error("Status code: " + str(result.status_code) + " Error: " + j.get("message") + " " +
                          json.dumps(j.get("details")))
                return ResponseError(j.get("message") + " " + json.dumps(j.get("details")))
        except Exception as e:
            LOG.exception(str(e))
            return ResponseError("Exception thrown when called getTable; Description: " + str(e))

    def searchTransaction(self) -> Response:
        pass
        try:
            path = '/v0/search/transactions'
            LOG.info("Path: " + path)
            LOG.info("Search transaction")

            LOG.debug("Request.get on path:" + path)
            result = DfuseConnection.retry(lambda: requests.get(
                self.link(path=path),
                params={},
                headers=self.headers(), verify=False))
            j = json.loads(result.text)
            if result.status_code == 200:
                LOG.success("Status code:200")
                return ResponseSuccessful(j)
            else:
                LOG.error("Status code: " + str(result.status_code) + " Error: " + j.get("message") + " " +
                          json.dumps(j.get("details")))
                return ResponseError(j.get("message") + " " + json.dumps(j.get("details")))
        except Exception as e:
            LOG.exception(str(e))


    def retry(func, ex_type=Exception, limit=5, wait_ms=100, wait_increase_ratio=2, logger=True):
        """
        Retry a function invocation until no exception occurs
        :param func: function to invoke
        :param ex_type: retry only if exception is subclass of this type
        :param limit: maximum number of invocation attempts
        :param wait_ms: initial wait time after each attempt in milliseconds.
        :param wait_increase_ratio: increase wait period by multiplying this value after each attempt.
        :param logger: if not None, retry attempts will be logged to this log.logger
        :return: result of first successful invocation
        :raises: last invocation exception if attempts exhausted or exception is not an instance of ex_type
        """
        attempt = 1
        while True:
            try:
                LOG_RETRY.info("Running the retry function " + str(attempt) + " times")
                return func()
            except Exception as ex:
                if not isinstance(ex, ex_type):
                    raise ex
                if 0 < limit <= attempt:
                    if logger:
                        LOG_RETRY.warning("No more attempts")
                    raise ex

                if logger:
                    LOG_RETRY.error("failed execution attempt " + str(attempt))

                attempt += 1
                if logger:
                    LOG_RETRY.info("waiting " + str(wait_ms) + " ms before attempt " + str(attempt))
                t.sleep(wait_ms / 1000)
                wait_ms *= wait_increase_ratio

def main():
    dfuseObj = DfuseConnection(dfuseApiKey=dfuse_api_key)
    test =dfuseObj.getTableRow(account="eosio.token", table="accounts", scope="b1", primaryKey="EOS")
    i = 9

if __name__ == "__main__":
    main()