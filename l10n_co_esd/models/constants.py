values = {
    'X509v3': 'http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-x509-token-profile-1.0#X509v3'
}

nsd = {
    'soap': 'http://www.w3.org/2003/05/soap-envelope',
    'wcf': 'http://wcf.dian.colombia',
    'wsse': 'http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd',
    'wsu': 'http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd',
    'wsa': 'http://www.w3.org/2005/08/addressing',
    'ds': 'http://www.w3.org/2000/09/xmldsig#',
}

actions = {
    'GetStatus': 'http://wcf.dian.colombia/IWcfDianCustomerServices/GetStatus',
    'GetStatusZip': 'http://wcf.dian.colombia/IWcfDianCustomerServices/GetStatusZip',
    'GetTaxPayer': 'http://wcf.dian.colombia/IWcfDianCustomerServices/GetTaxPayer',
    'GetXmlByDocumentKey': 'http://wcf.dian.colombia/IWcfDianCustomerServices/GetXmlByDocumentKey',
    'GetNumberingRange': 'http://wcf.dian.colombia/IWcfDianCustomerServices/GetNumberingRange',
    'SendTestSetAsync': 'http://wcf.dian.colombia/IWcfDianCustomerServices/SendTestSetAsync',
    'SendBillAsync': 'http://wcf.dian.colombia/IWcfDianCustomerServices/SendBillAsync',
    'SendBillSync': 'http://wcf.dian.colombia/IWcfDianCustomerServices/SendBillSync',
    'SendEventUpdateStatus': 'http://wcf.dian.colombia/IWcfDianCustomerServices/SendEventUpdateStatus',
}
