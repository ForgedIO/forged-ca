# ForgedCA

A simple, open-source ACME PKI platform built on [step-ca](https://smallstep.com/docs/step-ca/).

ForgedCA aims to be the easiest way to stand up a production-grade private PKI on-prem — Root, Intermediate, and Issuing CAs with ACME support, federated management, and painless trust-store deployment.

## Vision

- **Web-based installation wizard** — pick whether a server is a Root CA, Intermediate CA, Issuing CA, or all three
- **ACME with HTTP and DNS-01 validation**
- **Federated by default** — deploy additional servers and point them at the Root CA to auto-enroll an Intermediate or Issuing CA. Any node in the fleet can manage the entire PKI.
- **Trust-chain management** — easily fetch the full PEM chain or any individual certificate in the chain; supports multiple issuing and intermediate CAs
- **Trust-store deployment helpers** — wizards and instructions for GPO, Intune, and other distribution methods
- **Flexible cert lifetimes**
  - Root / Intermediate / Issuing CAs: long-term
  - ACME-issued leaf certs: short-term
  - Non-ACME server templates: anything less than the issuing CA lifetime
- **Revocation & OCSP** made simple
- **Dashboard** for a single-pane view of the entire PKI

## Status

Early development. Architecture and installer coming soon.

## Install

TBD — a single `install.sh` will provision nginx, the web platform, the database, and step-ca.

## License

TBD
