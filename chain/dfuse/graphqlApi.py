import json

from google.protobuf.struct_pb2 import Struct

from chain.dfuse import DfuseConnection, ResponseError, Response, ResponseSuccessful
from constants import dfuse_graphql_url
from log import Log
import ssl

import grpc
from chain.dfuse.graphqlV1 import graphql_pb2_grpc
from chain.dfuse.graphqlV1.graphql_pb2 import Request

ssl._create_default_https_context = ssl._create_unverified_context

LOG = Log(className="GraphQLApi")


class GraphQLApiException(Exception):
    pass


class GraphQLApi:
    def __init__(self, dfuseConnection: DfuseConnection):
        assert isinstance(dfuseConnection, DfuseConnection), "dfuseConnection must be type of DfuseConnection"
        try:
            LOG.info("Init GraphQLApi")
            self.dfuseConnection = dfuseConnection
            credentials = grpc.access_token_call_credentials(self.dfuseConnection.dfuseToken)

            channel = grpc.secure_channel(target=dfuse_graphql_url,
                                          credentials=grpc.composite_channel_credentials(
                                              grpc.ssl_channel_credentials(), credentials))

            LOG.debug("GraphQLApi.init: channel is successfully initialized")
            self.stub = graphql_pb2_grpc.GraphQLStub(channel)
            LOG.debug("GraphQLApi.init: stub is successfully initialized")
        except Exception as e:
            LOG.exception("Error in GraphQLApi: " + str(e))
            raise GraphQLApiException("Error in GraphQLApi.init: " + str(e))

    def getActionsVideoUploaded(self, account: str, startBlockNum: int, endBlockNum: int) -> list:
        assert isinstance(account, str), "account must be type of str"  # where smart contract is deployed
        assert isinstance(startBlockNum, int), "startBlockNum must be type of int"
        assert isinstance(endBlockNum, int), "endBlockNum must be type of int"
        try:
            #function returns list of json objects
            LOG.debug("Check if video is uploaded on account: " + account +
                      " from block: " + str(startBlockNum) +
                      " to block: " + str(endBlockNum))

            graphQlStub = self.stub

            _ACTION: str = "searchTransactionsForward"
            _CURSOR: str = "cursor"

            query: str = '''
                query ($query: String!, $cursor: String, $limit: Int64, $low: Int64, $high: Int64) {
                  ''' + _ACTION + '''(query: $query, lowBlockNum: $low, highBlockNum: $high, 
                    limit: $limit, cursor: $cursor, irreversibleOnly: true) {
                    cursor
                    results {
                      trace {
                        id
                        matchingActions {
                          data
                        }
                      }
                    }
                  }
                }
            '''

            toReturn: list = []

            variables = Struct()
            variables["query"] = "account:" + account + " action:electvideo"
            variables["low"] = startBlockNum
            variables["high"] = endBlockNum
            variables[_CURSOR] = ''  # at the beginning cursor is empty
            variables["limit"] = 10

            while True:
                queryResponse = graphQlStub.Execute(Request(query=query, variables=variables))  # variables=variables

                for rawResult in queryResponse:
                    if rawResult.errors:
                        # something went wrong
                        LOG.error("An error occurred while getting data from GraphQL" + str(rawResult.errors))
                        return ResponseError(error="An error occurred while getting data from GraphQL" +
                                                   str(rawResult.errors))
                    else:
                        # everything is ok
                        result = json.loads(rawResult.data)
                        if len(result[_ACTION]['results']) == 0:
                            # no more data - return what we have
                            return ResponseSuccessful(data=toReturn)
                        else:
                            # there is more data - add it to the list and continue from the last cursor
                            toReturn.extend(result[_ACTION]['results'])
                            variables[_CURSOR] = result[_ACTION][_CURSOR]
        except Exception as e:
            LOG.exception("Error in GraphQLApi.getActionsVideoUploaded: " + str(e))
            return ResponseError(error="Error in GraphQLApi.getActionsVideoUploaded: " + str(e))

