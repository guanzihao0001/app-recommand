FROM sunmi-docker-images-registry.cn-hangzhou.cr.aliyuncs.com/public/ubuntu:18.04
LABEL maintainer = "yuehui.wang@sunmi.com"

ENV DEBIAN_FRONTEND noninteractive
RUN sed -i s/archive.ubuntu.com/mirrors.tuna.tsinghua.edu.cn/g /etc/apt/sources.list && \
    sed -i s/security.ubuntu.com/mirrors.tuna.tsinghua.edu.cn/g /etc/apt/sources.list

RUN apt-get update
RUN apt-get install --assume-yes apt-utils
RUN apt-get install -y git libglib2.0-0 libsm6 libxext6 libxrender1 gcc python3-dev python3-pip tzdata ffmpeg vim htop
RUN pip3 install --upgrade pip -i https://mirrors.aliyun.com/pypi/simple
#RUN git clone http://gitlab+deploy-token-1021:AHibbVhuWvbn2xa-zDgM@code.sunmi.com/AI/heatmap.git
ENV REPO_ROOT=/app-recommend
COPY . $REPO_ROOT
WORKDIR $REPO_ROOT
RUN mkdir /logs
RUN pip3 install scikit-build cmake -i https://mirrors.aliyun.com/pypi/simple && \
    pip3 install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple

# RUN python3 -m grpc_tools.protoc --python_out=. --grpc_python_out=. -I. protobuf/inference_head_detection.proto

ENV DEBIAN_FRONTEND noninteractive
RUN ln -fs /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
 && echo 'Asia/Shanghai' >/etc/timezone
RUN dpkg-reconfigure -f noninteractive tzdata

ENV LC_ALL "C.UTF-8"
ENV LANG "C.UTF-8"
ENV C_FORCE_ROOT "true"

EXPOSE 5000

RUN chmod +x entrypoint.sh
ENTRYPOINT [ "./entrypoint.sh" ]
