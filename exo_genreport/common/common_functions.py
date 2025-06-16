def have_categories_and_concepts(version):
    res = {
        'has_categories': False if version.scenario == 'b' else True,
        'has_concepts': False if version.scenario == 'c' else True,
        'has_parameters': version.has_parameters,
        'scenario': version.scenario,
    }
    return res
