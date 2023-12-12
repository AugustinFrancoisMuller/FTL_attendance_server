# FTL_attendance_server 

FTL attendance server is the QRcode generation 

(FTL: Faster Than Light)

## For local devlopement:

### requirement

dotnet

install dotnet repo:
https://learn.microsoft.com/en-us/dotnet/core/install/linux-debian

(.NET 6 is used because of LTS release)

debian:
```
sudo apt-get install dotnet-sdk-6.0 libgdiplus
```


## For Docker devlopement:

```
docker build -t ftl .
docker run -p 8000:80 ftl
```

Connect to the webpage

http://127.0.0.1:8000


## Generation of the code

c# builtin random with new unknow seed each for iteration