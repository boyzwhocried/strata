{#
  Use the +schema config value literally (bronze / silver / gold) instead of
  dbt's default of prefixing it with the target schema. Keeps the warehouse
  layout readable and matches the medallion layer names exactly.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
