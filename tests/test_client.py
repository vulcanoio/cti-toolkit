""" TAXII client tests.

    The SimpleTaxiiClient encapsulates the libtaxii.clients.HttpClient,
    configuring it using the passed in configargparse instance.
"""
import httpretty
import libtaxii.clients
import xmltodict

import options_mock
import certau.client


class TestClient(object):
    """ Basic high-level tests of the transform functionality.
    """
    def test_client_creation(self):
        """ Test that the instantiation of a TAXII client sets up the libtaxii
            HttpClient correctly, based on the passed-in options.
        """
        # Enabling SSL and providing a username stores the username, password,
        # key file and cert file in the instance's auth credentials. It also
        # sets the authentication mode to AUTH_CERT_BASIC and enables HTTPS.
        options = options_mock.TaxiiClientOptions({
            'ssl': True,
            'username': 'user',
            'password': 'pass',
            'key': '/path1',
            'cert': '/path2',
        })
        taxii_client = certau.client.SimpleTaxiiClient(options)

        assert taxii_client.auth_credentials == {
            'username': 'user',
            'password': 'pass',
            'key_file': '/path1',
            'cert_file': '/path2',
        }

        assert taxii_client.auth_type == libtaxii.clients.HttpClient.AUTH_CERT_BASIC

        assert taxii_client.use_https

        # Enabling SSL but not providing a username stores only the key file
        # and cert file in the instance's auth credentials. It sets the
        # authentication mode to AUTH_CERT and enables HTTPS.
        options = options_mock.TaxiiClientOptions({
            'ssl': True,
            'key': '/path1',
            'cert': '/path2',
        })
        taxii_client = certau.client.SimpleTaxiiClient(options)

        assert taxii_client.auth_credentials == {
            'key_file': '/path1',
            'cert_file': '/path2',
        }

        assert taxii_client.auth_type == libtaxii.clients.HttpClient.AUTH_CERT

        assert taxii_client.use_https

        # Providing a username but not enabling SSL stores only the username
        # and password in the instance's auth credentials. It sets the
        # authentication mode to AUTH_BASIC but does not enable HTTPS.
        options = options_mock.TaxiiClientOptions({
            'username': 'user',
            'password': 'pass',
        })
        taxii_client = certau.client.SimpleTaxiiClient(options)

        assert taxii_client.auth_credentials == {
            'username': 'user',
            'password': 'pass',
        }

        assert taxii_client.auth_type == libtaxii.clients.HttpClient.AUTH_BASIC

        assert taxii_client.use_https is False

    def test_create_poll_request(self):
        """ Test the creations of a libtaxii PollRequest based on the
            passed-in options.
        """
        # Minimal poll request
        options = options_mock.TaxiiClientOptions({
            'username': 'user',
            'password': 'pass',
        })
        taxii_client = certau.client.SimpleTaxiiClient(options)
        poll_request = taxii_client.create_poll_request()
        poll_request_d = poll_request.to_dict()

        # The message id changes
        del poll_request_d['message_id']
        assert poll_request_d == {
            'extended_headers': {},
            'collection_name': 'my_collection',
            'message_type': 'Poll_Request',
            'poll_parameters': {
                'content_bindings': [],
                'query': None,
                'allow_asynch': 'false',
                'response_type': 'FULL',
                'delivery_parameters': None,
            },
        }

        # Including start and/or end date
        options = options_mock.TaxiiClientOptions({
            'username': 'user',
            'password': 'pass',
            'begin_ts': '2015-12-30T10:13:05.00000+10:00',
        })
        taxii_client = certau.client.SimpleTaxiiClient(options)
        poll_request = taxii_client.create_poll_request()
        poll_request_d = poll_request.to_dict()
        del poll_request_d['message_id']

        assert poll_request_d == {
            'extended_headers': {},
            'collection_name': 'my_collection',
            'message_type': 'Poll_Request',
            'poll_parameters': {
                'content_bindings': [],
                'query': None,
                'allow_asynch': 'false',
                'response_type': 'FULL',
                'delivery_parameters': None,
            },
            'exclusive_begin_timestamp_label': '2015-12-30T10:13:05+10:00',
        }

        options = options_mock.TaxiiClientOptions({
            'username': 'user',
            'password': 'pass',
            'begin_ts': '2015-12-30T10:13:05.00000+10:00',
            'end_ts': '2015-12-30T18:09:43.00000+10:00',
        })
        taxii_client = certau.client.SimpleTaxiiClient(options)
        poll_request = taxii_client.create_poll_request()
        poll_request_d = poll_request.to_dict()
        del poll_request_d['message_id']

        assert poll_request_d == {
            'extended_headers': {},
            'collection_name': 'my_collection',
            'message_type': 'Poll_Request',
            'poll_parameters': {
                'content_bindings': [],
                'query': None,
                'allow_asynch': 'false',
                'response_type': 'FULL',
                'delivery_parameters': None,
            },
            'exclusive_begin_timestamp_label': '2015-12-30T10:13:05+10:00',
            'inclusive_end_timestamp_label': '2015-12-30T18:09:43+10:00',
        }

        # Including a subscription id replaces the poll_parameters
        options = options_mock.TaxiiClientOptions({
            'username': 'user',
            'password': 'pass',
            'subscription_id': '2973847897'
        })
        taxii_client = certau.client.SimpleTaxiiClient(options)
        poll_request = taxii_client.create_poll_request()
        poll_request_d = poll_request.to_dict()
        del poll_request_d['message_id']

        assert poll_request_d == {
            'extended_headers': {},
            'collection_name': 'my_collection',
            'message_type': 'Poll_Request',
            'subscription_id': '2973847897',
            'poll_parameters': None,
        }

    @httpretty.activate
    def test_send_poll_request(self):
        """ Test the sending of a configured poll request.
        """
        # Ensures that non-registered paths fail
        httpretty.HTTPretty.allow_net_connect = False

        # Mock the TAXII endpoint enough to send it a request
        httpretty.register_uri(
            httpretty.POST, 'http://example.com:80/taxii_endpoint',
            body=lambda request, uri, headers: (200, {}, 'OK'),
        )

        # Configure a client and make a poll request
        options = options_mock.TaxiiClientOptions({
            'username': 'user',
            'password': 'pass',
            'begin_ts': '2015-12-30T10:13:05.00000+10:00',
            'end_ts': '2015-12-30T18:09:43.00000+10:00',
            'hostname': 'example.com',
            'path': '/taxii_endpoint',
        })
        taxii_client = certau.client.SimpleTaxiiClient(options)
        taxii_client.send_poll_request()

        # Capture the client request data
        request = httpretty.last_request()

        # Remove non-repeatable headers
        headers = request.headers.dict
        del headers['content-length']

        # Check we have the correct request headers
        assert request.headers.dict == {
            'x-taxii-accept': 'urn:taxii.mitre.org:message:xml:1.1',
            'x-taxii-protocol': 'urn:taxii.mitre.org:protocol:http:1.0',
            'accept-encoding': 'identity',
            'user-agent': 'libtaxii.httpclient',
            'connection': 'close',
            'accept': 'application/xml',
            'x-taxii-content-type': 'urn:taxii.mitre.org:message:xml:1.1',
            'host': 'example.com:80',
            'x-taxii-services': 'urn:taxii.mitre.org:services:1.1',
            'content-type': 'application/xml',
            'authorization': 'Basic dXNlcjpwYXNz'
        }

        # Create a dict representation of the body XML
        dictbody = xmltodict.parse(request.body, dict_constructor=dict)

        # Remove non-repeatable items
        del dictbody['taxii_11:Poll_Request']['@message_id']

        # Check we have the correct request body
        assert dictbody == {
            u'taxii_11:Poll_Request': {
                u'@xmlns:taxii': u'http://taxii.mitre.org/messages/taxii_xml_binding-1',
                u'taxii_11:Inclusive_End_Timestamp': u'2015-12-30T18:09:43+10:00',
                u'@xmlns:taxii_11': u'http://taxii.mitre.org/messages/taxii_xml_binding-1.1',
                u'@collection_name': u'my_collection',
                u'@xmlns:tdq': u'http://taxii.mitre.org/query/taxii_default_query-1',
                u'taxii_11:Poll_Parameters': {
                    u'taxii_11:Response_Type': u'FULL',
                    u'@allow_asynch': u'false'
                },
                u'taxii_11:Exclusive_Begin_Timestamp': u'2015-12-30T10:13:05+10:00'
            }
        }