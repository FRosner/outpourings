---
title: Deploying an HTTP API on AWS using Lambda and API Gateway
published: false
description:
tags:
cover_image:
---

# Introduction

- serverless

# Architecture




# Different Lambda Runtimes

- Java
  - Java is slow due to classloading (up to 100 times compared to Node.js, e.g.)
  - Put more memory to have more CPU as both are scaled based on memory (1024 mb)


# API Gateway Response

```JSON
{
  "body": "{\"test\":\"body\"}",
  "resource": "/{proxy+}",
  "requestContext": {
    "resourceId": "123456",
    "apiId": "1234567890",
    "resourcePath": "/{proxy+}",
    "httpMethod": "POST",
    "requestId": "c6af9ac6-7b61-11e6-9a41-93e8deadbeef",
    "accountId": "123456789012",
    "identity": {
      "apiKey": null,
      "userArn": null,
      "cognitoAuthenticationType": null,
      "caller": null,
      "userAgent": "Custom User Agent String",
      "user": null,
      "cognitoIdentityPoolId": null,
      "cognitoIdentityId": null,
      "cognitoAuthenticationProvider": null,
      "sourceIp": "127.0.0.1",
      "accountId": null
    },
    "stage": "prod"
  },
  "queryStringParameters": {
    "foo": "bar"
  },
  "headers": {
    "Via": "1.1 08f323deadbeefa7af34d5feb414ce27.cloudfront.net (CloudFront)",
    "Accept-Language": "en-US,en;q=0.8",
    "CloudFront-Is-Desktop-Viewer": "true",
    "CloudFront-Is-SmartTV-Viewer": "false",
    "CloudFront-Is-Mobile-Viewer": "false",
    "X-Forwarded-For": "127.0.0.1, 127.0.0.2",
    "CloudFront-Viewer-Country": "US",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Upgrade-Insecure-Requests": "1",
    "X-Forwarded-Port": "443",
    "Host": "1234567890.execute-api.us-east-1.amazonaws.com",
    "X-Forwarded-Proto": "https",
    "X-Amz-Cf-Id": "cDehVQoZnx43VYQb9j2-nvCh-9z396Uhbp027Y2JvkCPNLmGJHqlaA==",
    "CloudFront-Is-Tablet-Viewer": "false",
    "Cache-Control": "max-age=0",
    "User-Agent": "Custom User Agent String",
    "CloudFront-Forwarded-Proto": "https",
    "Accept-Encoding": "gzip, deflate, sdch"
  },
  "pathParameters": {
    "proxy": "path/to/resource"
  },
  "httpMethod": "POST",
  "stageVariables": {
    "baz": "qux"
  },
  "path": "/path/to/resource"
}
```

```JSON
{
  "isBase64Encoded": false,
  "statusCode": 200,
  "headers": {},
  "body": {
    "input": $input,
    "message": $output
  }
}
```

```JSON
{
  "message": "Hello me!",
  "input": {}
}
```
//    JSONObject responseBody = new JSONObject();
//    responseBody.put("input", event.toJSONString());
//    responseBody.put("message", greeting);
//
//    JSONObject headerJson = new JSONObject();
//    headerJson.put("x-custom-header", "my custom header value");
//
//    responseJson.put("isBase64Encoded", false);
//    responseJson.put("statusCode", responseCode);
//    responseJson.put("headers", headerJson);
//    responseJson.put("body", responseBody.toString());
```
