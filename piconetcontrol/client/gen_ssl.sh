#!/bin/bash

openssl ecparam -genkey -name prime256v1 -out ec_key.pem
openssl req -new -key ec_key.pem -out ec_csr.pem -subj "/CN=PicoW"
openssl req -x509 -key ec_key.pem -in ec_csr.pem -out ec_cert.pem -days 1000
openssl x509 -in ec_cert.pem -outform DER -out ec_cert.der
openssl ec -in ec_key.pem -outform DER -out ec_key.der
