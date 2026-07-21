{{- define "agency.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "agency.fullname" -}}
{{- printf "%s-%s" .Release.Name (include "agency.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
