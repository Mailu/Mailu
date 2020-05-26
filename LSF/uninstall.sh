#!/bin/bash
kubectl delete -f ingress.yaml
kubectl delete -f webdav.yaml
kubectl delete -f admin.yaml
kubectl delete -f fetchmail.yaml
kubectl delete -f smtp.yaml
kubectl delete -f security.yaml
kubectl delete -f imap.yaml
kubectl delete -f webmail.yaml
kubectl delete -f front.yaml
kubectl delete -f redis.yaml
kubectl delete -f pvc.yaml
kubectl delete -f configmap.yaml
kubectl delete -f rbac.yaml
