from abc import ABC, abstractmethod
import json, ast


class ParserElement:

    def __init__(self, data: bytes):
        self.data = data
        #self.schemaElement = schemaElement

    @abstractmethod
    def parse(self):
        pass

class ParserElementString (ParserElement):

    def parse(self, ):



class ProtobufParser:
    def __init__(self, schemaStr: str):
        #schema must be the same as on chain (atomic assets)
        if len(schemaStr) == 0:
            print("schema should not be empty")
        self.schema = ast.literal_eval(schemaStr)
        f = 8

    def getSchemaElement(self, index: int) ->{}:
        if index >= len(self.schema):
            print("Schema index: out of range")
        return self.schema[index]

    #def getTypeFromSchema(self, index: int) -> ():

    def parse(self, data: bytes) -> []:
        if bytes.





def main():
    print("Hello World!")
    schema = '[ { "name": "account", "type": "string" }, { "name": "name", "type": "string" }, { "name": "img", "type": "ipfs" }, { "name": "bio", "type": "string" }, { "name": "social", "type": "string" }, { "name": "video", "type": "ipfs" }, { "name": "attributions", "type": "string" } ]'
    ret = ProtobufParser(schema)

if __name__ == "__main__":
    main()
