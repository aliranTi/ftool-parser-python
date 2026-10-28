"""Parâmetros editáveis, em unidades de apresentação, sem dependências científicas."""

import math
from dataclasses import replace
from collections.abc import Mapping

from .sizing_config import StickSizingConfig


class ParameterError(ValueError):
    pass


def parameter_fields(model, config=None, overrides=None):
    config = config or StickSizingConfig()
    fields = []

    def add(key, label, value, unit, group, minimum=0, exclusive=True, integer=False):
        fields.append(dict(key=key, label=label, value=value, unit=unit, group=group,
                           edited=key in (overrides or {}),
                           minimum=minimum, exclusive=exclusive, integer=integer))

    for index, section in enumerate(model.sections):
        group = f"Seção {index + 1}: {section.name}"
        for key, label, value, unit in (
            ('width_mm', 'Dimensão b', section.width * 1000, 'mm'),
            ('thickness_mm', 'Dimensão h', section.thickness * 1000, 'mm'),
            ('area_mm2', 'Área da seção na análise', section.area * 1e6, 'mm²'),
            ('inertia_mm4', 'Inércia na análise', section.inertia * 1e12, 'mm⁴'),
        ):
            add(f'sections.{index}.{key}', label, value, unit, group)
    for index, material in enumerate(model.materials):
        add(f'materials.{index}.elasticity_mpa', f'E: {material.name}',
            material.elasticity / 1e6, 'MPa', 'Materiais da análise')
    for key, label, unit in (
        ('characteristic_strength_mpa', 'Resistência característica à compressão', 'MPa'),
        ('mean_elasticity_mpa', 'E médio para flambagem', 'MPa'),
        ('kmod1', 'kmod1', ''), ('kmod2', 'kmod2', ''),
        ('gamma_m', 'γm', ''), ('beta_c', 'βc', ''),
    ):
        add(f'wood.{key}', label, getattr(config.wood, key), unit,
            'Madeira no dimensionamento', exclusive=key != 'beta_c')
    add('tension.ft0m_mpa', 'Resistência média à tração', config.tension.ft0m_mpa,
        'MPa', 'Madeira no dimensionamento')
    for key, label in (
        ('effective_length_factor', 'Fator de comprimento efetivo'),
        ('design_force_factor', 'Fator de força de compressão'),
        ('tension_force_factor', 'Fator de força de tração'),
        ('minimum_member_layers', 'Mínimo construtivo de camadas'),
    ):
        add(key, label, getattr(config, key), '', 'Dimensionamento',
            minimum=1 if key == 'minimum_member_layers' else 0,
            exclusive=key != 'minimum_member_layers', integer=key == 'minimum_member_layers')
    add('stick.commercial_length_mm', 'Comprimento comercial', config.stick.commercial_length_mm,
        'mm', 'Palitos e emendas')
    add('splice_overlap_mm', 'Sobreposição nas emendas', config.splice_overlap_mm,
        'mm', 'Palitos e emendas', exclusive=False)
    return fields


def apply_parameters(model, overrides=None):
    """Aplica somente campos alterados a um modelo recém-interpretado."""
    if overrides is None:
        overrides = {}
    if not isinstance(overrides, Mapping):
        raise ParameterError('parameters deve ser um objeto.')
    config = StickSizingConfig()
    definitions = {field['key']: field for field in parameter_fields(model, config)}
    for key, value in overrides.items():
        if key not in definitions:
            raise ParameterError(f'Parâmetro desconhecido: {key}')
        field = definitions[key]
        if (isinstance(value, bool) or not isinstance(value, (float, int))
                or not math.isfinite(value)):
            raise ParameterError(f"{field['label']}: informe um número finito.")
        if value < field['minimum'] or (field['exclusive'] and value == field['minimum']):
            raise ParameterError(f"{field['label']}: valor fora do intervalo permitido.")
        if field['integer'] and value != int(value):
            raise ParameterError(f"{field['label']}: informe um inteiro.")

    for index, section in enumerate(model.sections):
        prefix = f'sections.{index}.'
        dimensions_changed = any(prefix + key in overrides for key in ('width_mm', 'thickness_mm'))
        if dimensions_changed:
            section.width = overrides.get(prefix + 'width_mm', section.width * 1000) / 1000
            section.thickness = overrides.get(prefix + 'thickness_mm', section.thickness * 1000) / 1000
            if section.width <= 0 or section.thickness <= 0:
                raise ParameterError(f'Seção {section.name}: preencha ambas as dimensões positivas.')
            section.area = section.width * section.thickness
            section.inertia = section.width * section.thickness**3 / 12
            section.height = section.thickness
        if prefix + 'area_mm2' in overrides:
            section.area = overrides[prefix + 'area_mm2'] / 1e6
        if prefix + 'inertia_mm4' in overrides:
            section.inertia = overrides[prefix + 'inertia_mm4'] / 1e12
    for index, material in enumerate(model.materials):
        key = f'materials.{index}.elasticity_mpa'
        if key in overrides:
            material.elasticity = overrides[key] * 1e6
    try:
        nested = {}
        for group in ('wood', 'tension', 'stick'):
            values = {key.split('.')[1]: value for key, value in overrides.items()
                      if key.startswith(group + '.')}
            nested[group] = replace(getattr(config, group), **values)
        values = {key: int(value) if definitions[key]['integer'] else value
                  for key, value in overrides.items() if '.' not in key}
        config = replace(config, **nested, **values)
    except ValueError as exc:
        raise ParameterError(str(exc)) from exc
    return config
