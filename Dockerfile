FROM python:2.7-slim
ADD ./requirements.txt /google-manage-gce-floating-ip/requirements.txt
WORKDIR /google-manage-gce-floating-ip
RUN pip install -r /google-manage-gce-floating-ip/requirements.txt
ADD . /google-manage-gce-floating-ip
ADD ./startup.sh /google-manage-gce-floating-ip/startup.sh
RUN chmod +x /google-manage-gce-floating-ip/startup.sh
ENTRYPOINT ["/google-manage-gce-floating-ip/startup.sh"]
