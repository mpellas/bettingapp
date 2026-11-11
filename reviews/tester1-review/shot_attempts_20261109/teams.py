"""Team full name -> (NHL abbrev, arena lat, lon, UTC offset in standard time). Hardcoded, public info."""
T = {
 'Anaheim Ducks': ('ANA', 33.808, -117.877, -8), 'Boston Bruins': ('BOS', 42.366, -71.062, -5),
 'Buffalo Sabres': ('BUF', 42.875, -78.876, -5), 'Calgary Flames': ('CGY', 51.037, -114.052, -7),
 'Carolina Hurricanes': ('CAR', 35.803, -78.722, -5), 'Chicago Blackhawks': ('CHI', 41.881, -87.674, -6),
 'Colorado Avalanche': ('COL', 39.749, -105.008, -7), 'Columbus Blue Jackets': ('CBJ', 39.969, -83.006, -5),
 'Dallas Stars': ('DAL', 32.790, -96.810, -6), 'Detroit Red Wings': ('DET', 42.341, -83.055, -5),
 'Edmonton Oilers': ('EDM', 53.547, -113.498, -7), 'Florida Panthers': ('FLA', 26.158, -80.326, -5),
 'Los Angeles Kings': ('LAK', 34.043, -118.267, -8), 'Minnesota Wild': ('MIN', 44.945, -93.101, -6),
 'Montreal Canadiens': ('MTL', 45.496, -73.569, -5), 'Montréal Canadiens': ('MTL', 45.496, -73.569, -5),
 'Nashville Predators': ('NSH', 36.159, -86.779, -6), 'New Jersey Devils': ('NJD', 40.734, -74.171, -5),
 'New York Islanders': ('NYI', 40.712, -73.726, -5), 'New York Rangers': ('NYR', 40.751, -73.993, -5),
 'Ottawa Senators': ('OTT', 45.297, -75.927, -5), 'Philadelphia Flyers': ('PHI', 39.901, -75.172, -5),
 'Pittsburgh Penguins': ('PIT', 40.439, -79.989, -5), 'San Jose Sharks': ('SJS', 37.333, -121.901, -8),
 'Seattle Kraken': ('SEA', 47.622, -122.354, -8), 'St. Louis Blues': ('STL', 38.627, -90.203, -6),
 'Tampa Bay Lightning': ('TBL', 27.943, -82.452, -5), 'Toronto Maple Leafs': ('TOR', 43.643, -79.379, -5),
 'Utah Mammoth': ('UTA', 40.768, -111.901, -7), 'Utah Hockey Club': ('UTA', 40.768, -111.901, -7),
 'Vancouver Canucks': ('VAN', 49.278, -123.109, -8), 'Vegas Golden Knights': ('VGK', 36.103, -115.178, -8),
 'Washington Capitals': ('WSH', 38.898, -77.021, -5), 'Winnipeg Jets': ('WPG', 49.893, -97.144, -6),
}
BY_ABBR = {v[0]: v for v in T.values()}
def miles(a, b):
    import math
    (la1, lo1), (la2, lo2) = [(math.radians(x[1]), math.radians(x[2])) for x in (a, b)]
    h = math.sin((la2-la1)/2)**2 + math.cos(la1)*math.cos(la2)*math.sin((lo2-lo1)/2)**2
    return 3958.8 * 2 * math.asin(math.sqrt(h))
def home_of(game):
    """'Away at Home' -> home full name."""
    return game.split(' at ')[-1].strip() if isinstance(game, str) and ' at ' in game else None
