import * as cdk from "aws-cdk-lib";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as ecr from "aws-cdk-lib/aws-ecr";
import * as ecs from "aws-cdk-lib/aws-ecs";
import * as ecsPatterns from "aws-cdk-lib/aws-ecs-patterns";
import * as elasticache from "aws-cdk-lib/aws-elasticache";
import * as elbv2 from "aws-cdk-lib/aws-elasticloadbalancingv2";
import * as iam from "aws-cdk-lib/aws-iam";
import * as logs from "aws-cdk-lib/aws-logs";
import * as rds from "aws-cdk-lib/aws-rds";
import * as secretsmanager from "aws-cdk-lib/aws-secretsmanager";
import { Construct } from "constructs";

export interface MonitoringPlatformStackProps extends cdk.StackProps {
  /** Container image tag pushed to ECR (default: latest). */
  readonly imageTag?: string;
  /** Allowed browser origins for CORS (comma-separated). */
  readonly corsOrigins?: string;
}

export class MonitoringPlatformStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: MonitoringPlatformStackProps = {}) {
    super(scope, id, props);

    const imageTag = props.imageTag ?? "latest";
    const databaseName = "monitoring";
    const corsOrigins = props.corsOrigins ?? "http://localhost:3000";

    const vpc = new ec2.Vpc(this, "Vpc", {
      maxAzs: 2,
      natGateways: 1,
      subnetConfiguration: [
        {
          name: "public",
          subnetType: ec2.SubnetType.PUBLIC,
          cidrMask: 24,
        },
        {
          name: "private",
          subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
          cidrMask: 24,
        },
      ],
    });

    const database = new rds.DatabaseCluster(this, "Database", {
      engine: rds.DatabaseClusterEngine.auroraPostgres({
        version: rds.AuroraPostgresEngineVersion.VER_16_4,
      }),
      credentials: rds.Credentials.fromGeneratedSecret("monitoring", {
        secretName: `${id.toLowerCase()}/database`,
      }),
      defaultDatabaseName: databaseName,
      serverlessV2MinCapacity: 0.5,
      serverlessV2MaxCapacity: 1,
      writer: rds.ClusterInstance.serverlessV2("Writer"),
      vpc,
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      deletionProtection: false,
      storageEncrypted: true,
    });

    const redisSecurityGroup = new ec2.SecurityGroup(this, "RedisSecurityGroup", {
      vpc,
      description: "ElastiCache Serverless Redis access from ECS tasks",
      allowAllOutbound: false,
    });

    const redis = new elasticache.CfnServerlessCache(this, "Redis", {
      serverlessCacheName: `${id.toLowerCase()}-redis`.slice(0, 40),
      engine: "redis",
      majorEngineVersion: "7",
      subnetIds: vpc.selectSubnets({
        subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
      }).subnetIds,
      securityGroupIds: [redisSecurityGroup.securityGroupId],
    });

    const appSecret = new secretsmanager.Secret(this, "AppSecret", {
      secretName: `${id.toLowerCase()}/app`,
      generateSecretString: {
        secretStringTemplate: JSON.stringify({}),
        generateStringKey: "JWT_SECRET",
        excludePunctuation: true,
        passwordLength: 48,
      },
    });

    const repository = new ecr.Repository(this, "BackendRepository", {
      repositoryName: `${id.toLowerCase()}-backend`,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      emptyOnDelete: true,
      imageScanOnPush: true,
    });

    const cluster = new ecs.Cluster(this, "Cluster", {
      vpc,
      containerInsights: true,
    });

    const logGroup = new logs.LogGroup(this, "ServiceLogs", {
      retention: logs.RetentionDays.ONE_WEEK,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    const commonEnvironment = {
      ENVIRONMENT: "staging",
      LOG_LEVEL: "INFO",
      ENABLE_API_DOCS: "true",
      WEB_CONCURRENCY: "1",
      DB_NAME: databaseName,
      DB_PORT: "5432",
      REDIS_DB: "0",
      CORS_ORIGINS: corsOrigins,
      FRONTEND_URL: corsOrigins.split(",")[0]?.trim() ?? corsOrigins,
    };

    const commonSecrets = {
      DB_USERNAME: ecs.Secret.fromSecretsManager(database.secret!, "username"),
      DB_PASSWORD: ecs.Secret.fromSecretsManager(database.secret!, "password"),
      JWT_SECRET: ecs.Secret.fromSecretsManager(appSecret, "JWT_SECRET"),
    };

    const apiService = new ecsPatterns.ApplicationLoadBalancedFargateService(
      this,
      "ApiService",
      {
        cluster,
        cpu: 256,
        memoryLimitMiB: 512,
        desiredCount: 1,
        publicLoadBalancer: true,
        assignPublicIp: false,
        taskSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
        listenerPort: 80,
        protocol: elbv2.ApplicationProtocol.HTTP,
        redirectHTTP: false,
        healthCheckGracePeriod: cdk.Duration.seconds(120),
        taskImageOptions: {
          image: ecs.ContainerImage.fromEcrRepository(repository, imageTag),
          containerPort: 8000,
          environment: {
            ...commonEnvironment,
            DB_HOST: database.clusterEndpoint.hostname,
            REDIS_HOST: redis.attrEndpointAddress,
            REDIS_PORT: redis.attrEndpointPort,
          },
          secrets: commonSecrets,
          logDriver: ecs.LogDrivers.awsLogs({
            streamPrefix: "api",
            logGroup,
          }),
        },
      },
    );

    apiService.targetGroup.configureHealthCheck({
      path: "/health/ready",
      healthyHttpCodes: "200",
      interval: cdk.Duration.seconds(30),
      timeout: cdk.Duration.seconds(10),
    });

    const taskSecurityGroup = apiService.service.connections.securityGroups[0];
    database.connections.allowDefaultPortFrom(taskSecurityGroup, "ECS tasks to Aurora");
    redisSecurityGroup.addIngressRule(
      taskSecurityGroup,
      ec2.Port.tcp(6379),
      "ECS tasks to Redis",
    );

    const backendImage = ecs.ContainerImage.fromEcrRepository(repository, imageTag);
    const baseTaskProps = {
      cpu: 256,
      memoryLimitMiB: 512,
      executionRole: apiService.taskDefinition.executionRole!,
      taskRole: apiService.taskDefinition.taskRole!,
    };

    const workerTask = new ecs.FargateTaskDefinition(this, "WorkerTask", baseTaskProps);
    workerTask.addContainer("Worker", {
      image: backendImage,
      logging: ecs.LogDrivers.awsLogs({ streamPrefix: "worker", logGroup }),
      environment: {
        ...commonEnvironment,
        DB_HOST: database.clusterEndpoint.hostname,
        REDIS_HOST: redis.attrEndpointAddress,
        REDIS_PORT: redis.attrEndpointPort,
      },
      secrets: commonSecrets,
      command: [
        "celery",
        "-A",
        "app.monitoring.celery_app",
        "worker",
        "--loglevel=info",
        "--concurrency=2",
        "-Q",
        "monitoring",
      ],
    });

    new ecs.FargateService(this, "WorkerService", {
      cluster,
      taskDefinition: workerTask,
      desiredCount: 1,
      assignPublicIp: false,
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
      securityGroups: [taskSecurityGroup],
    });

    const schedulerTask = new ecs.FargateTaskDefinition(this, "SchedulerTask", baseTaskProps);
    schedulerTask.addContainer("Scheduler", {
      image: backendImage,
      logging: ecs.LogDrivers.awsLogs({ streamPrefix: "scheduler", logGroup }),
      environment: {
        ...commonEnvironment,
        DB_HOST: database.clusterEndpoint.hostname,
        REDIS_HOST: redis.attrEndpointAddress,
        REDIS_PORT: redis.attrEndpointPort,
      },
      secrets: commonSecrets,
      command: ["python", "-m", "app.monitoring.scheduler"],
    });

    new ecs.FargateService(this, "SchedulerService", {
      cluster,
      taskDefinition: schedulerTask,
      desiredCount: 1,
      assignPublicIp: false,
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
      securityGroups: [taskSecurityGroup],
    });

    apiService.taskDefinition.addToExecutionRolePolicy(
      new iam.PolicyStatement({
        actions: [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
        ],
        resources: ["*"],
      }),
    );

    new cdk.CfnOutput(this, "ApiUrl", {
      value: `http://${apiService.loadBalancer.loadBalancerDnsName}`,
      description: "Public API base URL (set NEXT_PUBLIC_API_URL to this for the frontend)",
    });

    new cdk.CfnOutput(this, "EcrRepositoryUri", {
      value: repository.repositoryUri,
      description: "Push the backend Docker image here before deploying services",
    });

    new cdk.CfnOutput(this, "DatabaseSecretArn", {
      value: database.secret!.secretArn,
      description: "Aurora credentials in Secrets Manager",
    });

    new cdk.CfnOutput(this, "AppSecretArn", {
      value: appSecret.secretArn,
      description: "JWT secret in Secrets Manager",
    });

    new cdk.CfnOutput(this, "RedisEndpoint", {
      value: `${redis.attrEndpointAddress}:${redis.attrEndpointPort}`,
      description: "ElastiCache Serverless Redis endpoint",
    });

    new cdk.CfnOutput(this, "CorsOriginsHint", {
      value: "Set CORS_ORIGINS to your frontend URL after deploying Amplify or another host",
    });
  }
}
