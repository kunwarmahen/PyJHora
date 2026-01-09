import React, { useState } from 'react';
import './LocationSearch.css';

// Get API URL from environment or use default
const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

/**
 * LocationSearch Component
 *
 * A user-friendly component that allows searching for locations
 * and automatically fills in latitude, longitude, and timezone.
 *
 * Usage:
 * <LocationSearch
 *   onLocationSelect={(location) => {
 *     setLatitude(location.latitude);
 *     setLongitude(location.longitude);
 *     setTimezone(location.timezone);
 *   }}
 * />
 */
const LocationSearch = ({ onLocationSelect, placeholder = "Search location (e.g., Chennai, India)" }) => {
    const [query, setQuery] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');

    const searchLocation = async () => {
        if (!query.trim()) {
            setError('Please enter a location');
            return;
        }

        setLoading(true);
        setError('');
        setSuccess('');

        try {
            const response = await fetch(`${API_URL}/api/location/search`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ query: query.trim() })
            });

            const data = await response.json();

            if (data.success) {
                setSuccess(`Found: ${data.place} (${data.latitude}, ${data.longitude})`);

                // Call the callback with location data
                if (onLocationSelect) {
                    onLocationSelect({
                        place: data.place,
                        latitude: data.latitude,
                        longitude: data.longitude,
                        timezone: data.timezone
                    });
                }
            } else {
                setError(data.message || 'Location not found');
            }
        } catch (err) {
            setError('Failed to search location. Please try again.');
            console.error('Location search error:', err);
        } finally {
            setLoading(false);
        }
    };

    const handleKeyPress = (e) => {
        if (e.key === 'Enter') {
            searchLocation();
        }
    };

    return (
        <div className="location-search-container">
            <div className="location-search-input-group">
                <input
                    type="text"
                    className="location-search-input"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    onKeyPress={handleKeyPress}
                    placeholder={placeholder}
                    disabled={loading}
                />
                <button
                    className="location-search-button"
                    onClick={searchLocation}
                    disabled={loading || !query.trim()}
                >
                    {loading ? (
                        <span className="loading-spinner">🔍</span>
                    ) : (
                        'Search'
                    )}
                </button>
            </div>

            {error && (
                <div className="location-search-error">
                    ⚠️ {error}
                </div>
            )}

            {success && (
                <div className="location-search-success">
                    ✓ {success}
                </div>
            )}

            <div className="location-search-hint">
                💡 Tip: Use format "City, Country" (e.g., "Mumbai, India", "New York, USA")
            </div>
        </div>
    );
};

export default LocationSearch;
