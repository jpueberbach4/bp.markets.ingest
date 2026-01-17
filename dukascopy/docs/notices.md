<u>MT4 is decoded.</u>

## **Notice: Endpoint down**

Update: Hi, as of this morning (2025-01-17) the public historical feed seems to be down. It gives a 503 error. It is not IP-based, since all my "other IPs" experience the same behavior. Even IPs I didnt use yet for anything so far. Also my two mobiles fail. 503 normally indicates a resource issue. So it may be broken.

The specific error is: **Error from cloudfront**

What is cloudfront?

Amazon CloudFront is a Content Delivery Network (CDN) service provided by Amazon Web Services (AWS). Its primary goal is to speed up the delivery of your website’s content—like images, videos, and data—to users all over the world.
+1

Why CloudFront is showing a 503

There are four common reasons why CloudFront might serve this error, AI says:

- Origin Capacity (The most common): The backend server (S3, an EC2 instance, or a Load Balancer) is overwhelmed by too many requests and is telling CloudFront it can't handle any more.

- Lambda@Edge or CloudFront Functions: If you use custom code to modify requests at the edge, a 503 often means that code crashed or hit a timeout limit (usually 10–30 seconds).

- S3 "Slow Down" Throttling: If you are using Amazon S3 as your source, S3 might be throttling CloudFront because you're hitting the request rate limit for a specific folder (prefix).

- CloudFront Resource Constraints: In rare cases, the specific CloudFront "edge location" closest to you might be experiencing temporary resource issues.

It seems an issue on the cloudprovider they use. A resource issue. It's definately not a ban/block.

https://downdetector.com/status/aws-amazon-web-services/

## Write-up

I have started with writing up everything i have learned so far in a document [performance.md](performance.md). This project was able to get institutional performance on just a laptop. The project excelled in getting data aligned right. The forementioned document will cover everything, from performance tricks up until market-data specific difficulties. Basically the what, the why and the how of this project. It will be an educational read including in-depth technical howto's.

I will keep you guys posted. Lets see what happens. It is too early to draw any conclusions.

**Note:** Development continues as planned. Data-api is now ready to make "buffered-charts". Updates soon.
