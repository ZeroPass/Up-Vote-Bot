# Generated by the gRPC Python protocol compiler plugin. DO NOT EDIT!
import grpc

from chain.dfuse.graphqlV1 import graphql_pb2 as dfuse_dot_graphql_dot_v1_dot_graphql__pb2


class GraphQLStub(object):
  # missing associated documentation comment in .proto file
  pass

  def __init__(self, channel):
    """Constructor.

    Args:
      channel: A grpc.Channel.
    """
    self.Execute = channel.unary_stream(
        '/dfuse.graphql.v1.GraphQL/Execute',
        request_serializer=dfuse_dot_graphql_dot_v1_dot_graphql__pb2.Request.SerializeToString,
        response_deserializer=dfuse_dot_graphql_dot_v1_dot_graphql__pb2.Response.FromString,
        )


class GraphQLServicer(object):
  # missing associated documentation comment in .proto file
  pass

  def Execute(self, request, context):
    # missing associated documentation comment in .proto file
    pass
    context.set_code(grpc.StatusCode.UNIMPLEMENTED)
    context.set_details('Method not implemented!')
    raise NotImplementedError('Method not implemented!')


def add_GraphQLServicer_to_server(servicer, server):
  rpc_method_handlers = {
      'Execute': grpc.unary_stream_rpc_method_handler(
          servicer.Execute,
          request_deserializer=dfuse_dot_graphql_dot_v1_dot_graphql__pb2.Request.FromString,
          response_serializer=dfuse_dot_graphql_dot_v1_dot_graphql__pb2.Response.SerializeToString,
      ),
  }
  generic_handler = grpc.method_handlers_generic_handler(
      'dfuse.graphql.v1.GraphQL', rpc_method_handlers)
  server.add_generic_rpc_handlers((generic_handler,))