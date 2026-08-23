#!/usr/bin/env node
import * as cdk from "aws-cdk-lib";
import { MonitoringPlatformStack } from "../lib/monitoring-platform-stack";

const app = new cdk.App();

const imageTag = app.node.tryGetContext("imageTag") ?? "latest";
const corsOrigins = app.node.tryGetContext("corsOrigins") ?? "http://localhost:3000";

new MonitoringPlatformStack(app, "RateLimiterDev", {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION ?? "us-east-1",
  },
  imageTag,
  corsOrigins,
  description: "Dev-sized AWS deployment for the API Monitoring Platform",
});
