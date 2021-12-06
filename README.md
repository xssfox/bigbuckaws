(Almost) Free Video Hosting provided by AWS Demo by [@xssfox](https://twitter.com/xssfox)
==

Ever wanted to host 1080p 60fps video but don't want to pay the hosting bill? By (ab)using some of AWS's features we can serve DVD quality content to a million clients for ~$10USD

[Demo video](http://bbb-lambda.s3-website.us-east-2.amazonaws.com/bbb.m3u8) 
--
(works in IE Edge, and Safari - to use Firefox or Chrome see links before; should also work in most modern media players)



How does it work?
--

AWS lets us upload 75GB of Lambda functions. Each function can be 50MB in size. We simply split up the video into Lambda functions. There's a few problems with this though, first off Lambda only allows zip files. How do we get around this, we zip up the video.

Now we have another problem, to play the video we'd need to unzip it. That's where we can do two little tricks, first when we zip up the file with 0% compression. This allows the original file to remain intact, but the zipping process just wraps some headers around the files (like a tarball). But video players aren't going to want to play a zip file, so that's where HLS standards come in to the rescue.

By using HLS we can split the file into multiple chunks and create a playlist of videos to play seamlessly together. A m3u8 HLS file looks something like this 
```
#EXTINF:31.600000,
bbb-0.ts
#EXTINF:28.833333,
bbb-1.ts
#EXTINF:32.000000,
```
what we do to the playlist file is make use of the `EXT-X-BYTERANGE` tag that allows us to tell the client where to get the bytes from. Using this we can skip past the zip header and straight to the actual content within the zip file. It looks something like this:
```
#EXTINF:31.600000,
#EXT-X-BYTERANGE:21118416@66
bbb-0.ts
#EXTINF:28.833333,
#EXT-X-BYTERANGE:19254396@66
bbb-1.ts
#EXTINF:32.000000,
#EXT-X-BYTERANGE:14320336@66
bbb-2.ts
```

The last little piece is working out how to get the client to download the data from AWS Lambda. AWS lets you download your uploaded code again, but the way it lets you do this is through a presigned url to an S3 bucket. All we need to do is call `get-function` and it provides the S3 presigned URL that's valid for 10 minutes. Media players aren't really going to understand this so we need to make it easier for them. Remember that this isn't your bucket, it's Amazons, so they pay the $$$.

This is where most of the expense comes into this system. The easiest way I found was to create an API Gateway and Lambda function that responds to requests for chunks with a redirect to the presigned URL. Eg media player says "can I have the first playlist item" to API gateway, API gateway fires the Lambda function that runs `get-function` and returns back to the media player with the presigned URL. We also perform some caching here so that we don't overwhelm AWS with `get-function` requests.

So our final m3u8 playlist looks something like this
```
#EXTINF:31.600000,
#EXT-X-BYTERANGE:21118416@66
https://mixpj3rk5d.execute-api.us-east-2.amazonaws.com/prod/0
#EXTINF:28.833333,
#EXT-X-BYTERANGE:19254396@66
https://mixpj3rk5d.execute-api.us-east-2.amazonaws.com/prod/1
#EXTINF:32.000000,
#EXT-X-BYTERANGE:14320336@66
https://mixpj3rk5d.execute-api.us-east-2.amazonaws.com/prod/2
```

and the links (`https://mixpj3rk5d.execute-api.us-east-2.amazonaws.com/prod/0`) end up redirecting to something that looks like this `https://awslambda-us-east-2-tasks.s3.us-east-2.amazonaws.com/snapshots/082208999166/bbb-0-7db00eaf-4c7a-4b18-b6bf-8be2424dee1d?versionId=O_...<snip>...1b749e9426408827fb5732e1d8ec305b11e2938a27a89d02e175a3c`

Just upload the m3u8 somewhere and your done.

Works in
==
 - Windows Media player
 - VLC 3.0.8
 - VLC Android
 - Safari
 - Edge
 - Firefox for Android
 - mplayer
 - Mxplayer 
 - Chrome with https://chrome.google.com/webstore/detail/play-hls-m3u8/ckblfoghkjhaclegefojbgllenffajdc extension
 - Firefox with https://addons.mozilla.org/en-US/firefox/addon/hls-js-playback/

Doesn't work in
==
- Chrome
- Firefox
- VLC versions before 3.0.8

Limitations
==
 - 75GB of storage per account
 - Can't embed due to CORS restrictions
 - Chrome and Firefox don't support playing HLS natively

How To
==

Rough instructions on how to replicate with your own videos. Should you use this? Probably not.
## Split up video
```
# create the ts files and m3u8
ffmpeg -y \
 -i bbb_sunflower_1080p_60fps_normal.mp4 \
 -codec copy \
 -bsf:v h264_mp4toannexb \
 -map 0 \
 -f segment \
 -segment_time 30 \
 -segment_format mpegts \
 -segment_list "bbb.m3u8" \
 -segment_list_type m3u8 \
 "bbb-%d.ts"

#zip them up so lambda accepts them (on fish shell) - 0 compression because we want to range to them

for i in (seq 0 21);  zip -r -0 bbb-$i.zip bbb-$i.ts; end


use xxd to find offsets (probably easier using zipinfo -v but this works)

# 1-9 = 66 offset
# 10+ = 67


# upload lambda functions
aws lambda create-function --region us-east-2 --function-name bbb-0 --runtime nodejs12.x --role "arn:aws:iam::082208999166:role/lambda_basic_execution" --handler "blah.blah" --zip-file fileb://bbb-0.zip

for i in (seq 0 21); aws lambda create-function --region us-east-2 --function-name bbb-$i --runtime nodejs12.x --role "arn:aws:iam::082208999166:role/lambda_basic_execution" --handler "blah.blah" --zip-file fileb://bbb-$i.zip; end
```


## Create the API Gateway / Lambda function
(really this should be CloudFormation but given I'm doing this as one off PoC that's left to the reader to build)
We need a way of getting the latest code download link. We use Lambda for this because it's dirt cheap. In front of Lambda we place API Gateway

Create a Lambda function from scratch, give it IAM permissions to read lambda functions, upload redirect.py as the the function code.

 - Create a new API Gateway in AWS
 - Create a `/{proxy+}` proxy method
 - Update Integration Request for the method to be Lambda Function and point it at the redirect Lambda
 - Deploy the api gateway. 

## Create the m3u8
ffmpeg Should have given you an m3u8, you need to modify that. Before every file we need to add the Byterange field. the first number is the length of the file (without zip) and the last number is the offset inside the zip (which we found with `xxd` earlier)
```
#EXT-X-BYTERANGE:19254396@66
```
Update the path to the file to point to your api gateway endpoint, eg `https://mixpj3rk5d.execute-api.us-east-2.amazonaws.com/prod/2`

You can probably script this.


Inspiration
==
Laurent Meyer did a [great write up](https://medium.com/@laurentmeyer/deep-dive-in-the-illegal-streaming-world-cd11fae63497) about Google Drive streamers using PNG to cover their tracks.
