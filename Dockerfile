FROM ubuntu:22.04

ENV LC_ALL C.UTF-8
ENV LANG C.UTF-8
ENV MY_VARIABLE my_value

RUN apt-get update -y \
    && apt-get upgrade -y \
    && apt-get dist-upgrade -y \
    && apt-get install -y --no-install-recommends \
    bash \
    build-essential \
    curl \
    git \
    librdkafka-dev \
    openssh-server \
    python3-pip \
    python3-setuptools \
    wget \
    && cd /usr/local/bin \
    && pip3 --no-cache-dir install --upgrade pip \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    && apt-get clean && rm -rf /var/lib/apt/lists/*


RUN apt-get remove --purge -y linux-libc-dev

WORKDIR /srv/catalyst
COPY ./requirements/requirements.txt .


RUN pip3 install --upgrade pip setuptools wheel && pip3 install -r ./requirements.txt


COPY . .
RUN git rev-parse HEAD > gitsha && rm -rf .git


WORKDIR /srv/catalyst
RUN mkdir -p /srv/catalyst/repos


EXPOSE 8081
RUN chmod +x ci-test.sh

ENV ENVIRONMENT docker
RUN python3 startup.py --all

ENTRYPOINT ["python3", "entrypoint.py"]
