{{- define "opencivic.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "opencivic.fullname" -}}
{{- printf "%s-%s" .Release.Name (include "opencivic.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "opencivic.databaseUrl" -}}
{{- if .Values.postgres.enabled -}}
postgresql+asyncpg://{{ .Values.postgres.auth.username }}:{{ .Values.postgres.auth.password }}@{{ include "opencivic.fullname" . }}-postgres:{{ .Values.postgres.service.port }}/{{ .Values.postgres.auth.database }}
{{- else -}}
{{ .Values.env.databaseUrl }}
{{- end -}}
{{- end -}}

{{- define "opencivic.valkeyUrl" -}}
{{- if .Values.valkey.enabled -}}
redis://:{{ .Values.valkey.auth.password }}@{{ include "opencivic.fullname" . }}-valkey:{{ .Values.valkey.service.port }}/0
{{- else -}}
{{ .Values.env.valkeyUrl }}
{{- end -}}
{{- end -}}

{{- define "opencivic.qdrantUrl" -}}
{{- if .Values.qdrant.enabled -}}
http://{{ include "opencivic.fullname" . }}-qdrant:{{ .Values.qdrant.service.port }}
{{- else -}}
{{ .Values.env.qdrantUrl }}
{{- end -}}
{{- end -}}

{{- define "opencivic.storageEndpoint" -}}
{{- if .Values.minio.enabled -}}
http://{{ include "opencivic.fullname" . }}-minio:{{ .Values.minio.service.port }}
{{- else -}}
{{ .Values.env.storageEndpoint }}
{{- end -}}
{{- end -}}
