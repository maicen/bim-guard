# Multi-stage build for osama-ata/OpenCDE that adds what its own repo
# Dockerfile (src/server/Dangl.OpenCDE/Dockerfile) deliberately skips: the
# Angular admin UI (dangl-opencde-ui). That upstream Dockerfile only builds
# the ASP.NET Core API, so the human-facing hand-shake pages 404 under it.
#
# This build clones the fork fresh, compiles dangl-opencde-ui with its own
# `build:production` script (which writes into
# src/server/Dangl.OpenCDE/wwwroot/dist/browser -- the exact static path
# Dangl.OpenCDE.Core's ConfigureOpenCdeApp serves as the SPA default page
# whenever ASPNETCORE_ENVIRONMENT is not Development), then publishes the
# API and layers the compiled UI on top.
ARG OPENCDE_REPO=https://github.com/osama-ata/OpenCDE.git
ARG OPENCDE_REF=develop

# Node 22, not 20: @supabase/supabase-js's sub-packages (storage-js,
# realtime-js, postgrest-js, functions-js) declare "engines": { "node": ">=22" }.
FROM node:22-bookworm AS ui-build
ARG OPENCDE_REPO
ARG OPENCDE_REF
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
RUN git clone --branch ${OPENCDE_REF} --depth 1 ${OPENCDE_REPO} /src
WORKDIR /src/src/server/dangl-opencde-ui
RUN npm ci
RUN npm run build:production

FROM mcr.microsoft.com/dotnet/sdk:8.0 AS api-build
ARG OPENCDE_REPO
ARG OPENCDE_REF
WORKDIR /src
RUN git clone --branch ${OPENCDE_REF} --depth 1 ${OPENCDE_REPO} .
RUN dotnet restore src/server/Dangl.OpenCDE/Dangl.OpenCDE.csproj
RUN dotnet publish src/server/Dangl.OpenCDE/Dangl.OpenCDE.csproj -c Release -o /app --no-restore

FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS final
WORKDIR /app
COPY --from=api-build /app .
COPY --from=ui-build /src/src/server/Dangl.OpenCDE/wwwroot/dist ./wwwroot/dist
EXPOSE 80
ENV ASPNETCORE_FORWARDEDHEADERS_ENABLED=true
ENV ASPNETCORE_URLS=http://*:80
ENTRYPOINT ["dotnet", "Dangl.OpenCDE.dll"]
