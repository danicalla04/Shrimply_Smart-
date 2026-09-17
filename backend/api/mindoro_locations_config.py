"""
Oriental Mindoro Municipalities Configuration
Includes geographic coordinates, weather API mappings, and ML model references
"""

ORIENTAL_MINDORO_MUNICIPALITIES = {
    # Calapan City - PRIMARY FOCUS (High Accuracy)
    'calapan': {
        'display_name': 'Calapan City',
        'full_name': 'Calapan City, Oriental Mindoro',
        'coordinates': {
            'latitude': 13.4138,
            'longitude': 121.1893,
        },
        'region': 'CALABARZON',
        'is_primary': True,
        'is_coastal': True,
        'elevation_m': 0,  # Port area
        'population_est': 78000,
        'weather_api_alias': 'calapan',
        'model_name': 'calapan',  # LSTM/XGBoost model name
    },
    
    # Secondary municipalities
    'puerto_galera': {
        'display_name': 'Puerto Galera',
        'full_name': 'Puerto Galera, Oriental Mindoro',
        'coordinates': {
            'latitude': 13.5039,
            'longitude': 120.9500,
        },
        'region': 'CALABARZON',
        'is_primary': False,
        'is_coastal': True,
        'elevation_m': 0,
        'population_est': 20000,
        'weather_api_alias': 'puerto_galera',
        'model_name': 'puerto_galera',
        'parent_municipality': None,
    },
    
    'san_teodoro': {
        'display_name': 'San Teodoro',
        'full_name': 'San Teodoro, Oriental Mindoro',
        'coordinates': {
            'latitude': 13.1333,
            'longitude': 121.3333,
        },
        'region': 'CALABARZON',
        'is_primary': False,
        'is_coastal': True,
        'elevation_m': 15,
        'population_est': 12000,
        'weather_api_alias': 'san_teodoro',
        'model_name': 'san_teodoro',
        'parent_municipality': None,
    },
    
    'baco': {
        'display_name': 'Baco',
        'full_name': 'Baco, Oriental Mindoro',
        'coordinates': {
            'latitude': 13.4167,
            'longitude': 121.5833,
        },
        'region': 'CALABARZON',
        'is_primary': False,
        'is_coastal': False,
        'elevation_m': 250,
        'population_est': 15000,
        'weather_api_alias': 'baco',
        'model_name': 'baco',
        'parent_municipality': None,
    },
    
    'naujan': {
        'display_name': 'Naujan',
        'full_name': 'Naujan, Oriental Mindoro',
        'coordinates': {
            'latitude': 13.4000,
            'longitude': 121.3833,
        },
        'region': 'CALABARZON',
        'is_primary': False,
        'is_coastal': False,
        'elevation_m': 100,
        'population_est': 25000,
        'weather_api_alias': 'naujan',
        'model_name': 'naujan',
        'parent_municipality': None,
    },
    
    'victoria': {
        'display_name': 'Victoria',
        'full_name': 'Victoria, Oriental Mindoro',
        'coordinates': {
            'latitude': 13.3500,
            'longitude': 121.0000,
        },
        'region': 'CALABARZON',
        'is_primary': False,
        'is_coastal': True,
        'elevation_m': 10,
        'population_est': 18000,
        'weather_api_alias': 'victoria',
        'model_name': 'victoria',
        'parent_municipality': None,
    },
    
    'socorro': {
        'display_name': 'Socorro',
        'full_name': 'Socorro, Oriental Mindoro',
        'coordinates': {
            'latitude': 13.4667,
            'longitude': 121.0833,
        },
        'region': 'CALABARZON',
        'is_primary': False,
        'is_coastal': True,
        'elevation_m': 5,
        'population_est': 8000,
        'weather_api_alias': 'socorro',
        'model_name': 'socorro',
        'parent_municipality': None,
    },
    
    'pola': {
        'display_name': 'Pola',
        'full_name': 'Pola, Oriental Mindoro',
        'coordinates': {
            'latitude': 13.5333,
            'longitude': 121.1833,
        },
        'region': 'CALABARZON',
        'is_primary': False,
        'is_coastal': True,
        'elevation_m': 2,
        'population_est': 5000,
        'weather_api_alias': 'pola',
        'model_name': 'pola',
        'parent_municipality': None,
    },
    
    'pinamalayan': {
        'display_name': 'Pinamalayan',
        'full_name': 'Pinamalayan, Oriental Mindoro',
        'coordinates': {
            'latitude': 13.0500,
            'longitude': 121.3333,
        },
        'region': 'CALABARZON',
        'is_primary': False,
        'is_coastal': False,
        'elevation_m': 50,
        'population_est': 30000,
        'weather_api_alias': 'pinamalayan',
        'model_name': 'pinamalayan',
        'parent_municipality': None,
    },
    
    'gloria': {
        'display_name': 'Gloria',
        'full_name': 'Gloria, Oriental Mindoro',
        'coordinates': {
            'latitude': 13.2833,
            'longitude': 121.2000,
        },
        'region': 'CALABARZON',
        'is_primary': False,
        'is_coastal': False,
        'elevation_m': 75,
        'population_est': 9000,
        'weather_api_alias': 'gloria',
        'model_name': 'gloria',
        'parent_municipality': None,
    },
    
    'bansud': {
        'display_name': 'Bansud',
        'full_name': 'Bansud, Oriental Mindoro',
        'coordinates': {
            'latitude': 12.9667,
            'longitude': 121.6000,
        },
        'region': 'CALABARZON',
        'is_primary': False,
        'is_coastal': True,
        'elevation_m': 8,
        'population_est': 22000,
        'weather_api_alias': 'bansud',
        'model_name': 'bansud',
        'parent_municipality': None,
    },
    
    'bongabong': {
        'display_name': 'Bongabong',
        'full_name': 'Bongabong, Oriental Mindoro',
        'coordinates': {
            'latitude': 13.1500,
            'longitude': 121.6167,
        },
        'region': 'CALABARZON',
        'is_primary': False,
        'is_coastal': False,
        'elevation_m': 100,
        'population_est': 19000,
        'weather_api_alias': 'bongabong',
        'model_name': 'bongabong',
        'parent_municipality': None,
    },
    
    'roxas': {
        'display_name': 'Roxas',
        'full_name': 'Roxas, Oriental Mindoro',
        'coordinates': {
            'latitude': 12.8333,
            'longitude': 121.5667,
        },
        'region': 'CALABARZON',
        'is_primary': False,
        'is_coastal': False,
        'elevation_m': 80,
        'population_est': 16000,
        'weather_api_alias': 'roxas',
        'model_name': 'roxas',
        'parent_municipality': None,
    },
    
    'mansalay': {
        'display_name': 'Mansalay',
        'full_name': 'Mansalay, Oriental Mindoro',
        'coordinates': {
            'latitude': 12.7667,
            'longitude': 121.7500,
        },
        'region': 'CALABARZON',
        'is_primary': False,
        'is_coastal': False,
        'elevation_m': 120,
        'population_est': 14000,
        'weather_api_alias': 'mansalay',
        'model_name': 'mansalay',
        'parent_municipality': None,
    },
    
    'bulalacao': {
        'display_name': 'Bulalacao',
        'full_name': 'Bulalacao, Oriental Mindoro',
        'coordinates': {
            'latitude': 12.5667,
            'longitude': 121.8500,
        },
        'region': 'CALABARZON',
        'is_primary': False,
        'is_coastal': True,
        'elevation_m': 5,
        'population_est': 11000,
        'weather_api_alias': 'bulalacao',
        'model_name': 'bulalacao',
        'parent_municipality': None,
    },
}


def get_municipality_config(location_key: str) -> dict:
    """Get configuration for a municipality by key."""
    location_key = location_key.lower().replace(' ', '_').replace('-', '_')
    return ORIENTAL_MINDORO_MUNICIPALITIES.get(location_key)


def get_all_municipalities() -> list:
    """Get list of all municipalities."""
    return list(ORIENTAL_MINDORO_MUNICIPALITIES.keys())


def get_all_municipalities_display() -> list:
    """Get list of municipalities with display names."""
    return [
        {
            'key': k,
            'display_name': v['display_name'],
            'is_primary': v['is_primary'],
            'is_coastal': v['is_coastal'],
            'coordinates': v['coordinates'],
        }
        for k, v in ORIENTAL_MINDORO_MUNICIPALITIES.items()
    ]


def get_primary_municipality() -> str:
    """Get the primary municipality (Calapan City)."""
    return 'calapan'


def get_coastal_municipalities() -> list:
    """Get list of coastal municipalities."""
    return [k for k, v in ORIENTAL_MINDORO_MUNICIPALITIES.items() if v['is_coastal']]


def get_municipality_coordinates(location_key: str) -> dict:
    """Get latitude/longitude for a municipality."""
    config = get_municipality_config(location_key)
    if config:
        return config['coordinates']
    return None


def get_nearest_municipality(latitude: float, longitude: float) -> str:
    """Find the nearest municipality to given coordinates."""
    from math import sqrt
    
    min_distance = float('inf')
    nearest = None
    
    for key, config in ORIENTAL_MINDORO_MUNICIPALITIES.items():
        coords = config['coordinates']
        distance = sqrt(
            (coords['latitude'] - latitude) ** 2 +
            (coords['longitude'] - longitude) ** 2
        )
        if distance < min_distance:
            min_distance = distance
            nearest = key
    
    return nearest


# Backward compatibility mappings
LOCATION_ALIASES = {
    'calapan': 'calapan',
    'calapan_city': 'calapan',
    'pinamalayan': 'pinamalayan',
    'oriental_mindoro': 'calapan',  # Default to Calapan City
    'mindoro': 'calapan',
}


def resolve_location(location: str) -> str:
    """Resolve location alias to canonical key."""
    location = location.lower().replace(' ', '_').replace('-', '_')
    
    # Check if it's already a valid key
    if location in ORIENTAL_MINDORO_MUNICIPALITIES:
        return location
    
    # Check aliases
    if location in LOCATION_ALIASES:
        return LOCATION_ALIASES[location]
    
    # Default to Calapan City
    return get_primary_municipality()
