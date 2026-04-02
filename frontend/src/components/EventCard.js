import React, { useState } from 'react';
import { format } from 'date-fns';
import { Calendar, MapPin, Tag, Bookmark, Layers, ChevronRight, ChevronLeft } from 'lucide-react';

/**
 * Component to handle description truncation and expansion
 */
const Description = ({ text, color }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  
    if (!text) return <p className="text-xs text-gray-700 mb-4 flex-1">No description provided.</p>;

  // Heuristic: only show toggle if text is reasonably long
  const shouldTruncate = text.length > 150;

  if (!shouldTruncate) {
            return (
                <p className="text-xs text-gray-700 mb-4 flex-1 pl-2 border-l-2" style={{ borderLeftColor: color || '#CBD5E1' }}>
                    {text}
                </p>
            );
  }

  return (
    <div className="mb-4 flex-1">
            <p
                className={`text-xs text-gray-700 pl-2 border-l-2 ${isExpanded ? '' : 'line-clamp-3'}`}
                style={{ borderLeftColor: color || '#CBD5E1' }}
            >
        {text}
      </p>
      <button 
        onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            setIsExpanded(!isExpanded);
        }}
        className="text-indigo-600 hover:text-indigo-800 text-xs font-medium mt-1 focus:outline-none"
      >
        {isExpanded ? 'Show less' : 'Read more'}
      </button>
    </div>
  );
};

/**
 * Helper to format the full date and time range string.
 * @param {string} start - ISO start time string.
 * @param {string} end - ISO end time string.
 * @returns {string} Formatted string like "Thu, Oct 12 • 6:00 PM - 9:00 PM"
 */
const formatDateTimeRange = (start, end) => {
  const startDate = new Date(start);
  const endDate = new Date(end);
  
  if (isNaN(startDate)) {
    return 'Date TBD';
  }

  // Format date: "Thu, Oct 12"
  const dateStr = format(startDate, 'EEE, MMM d');
  
  // Format times
  const startTime = format(startDate, 'h:mm a');
  let timeStr = startTime;

  if (!isNaN(endDate)) {
      const endTime = format(endDate, 'h:mm a');
      timeStr = `${startTime} - ${endTime}`;
  }

  return `${dateStr} • ${timeStr}`;
};

/**
 * Helper to determine the location string.
 * @param {object} event - The event object.
 * @returns {string} The location string.
 */
const getLocation = (event) => {
    if (event.location_type === 'online') return 'Online';
    return event.city || 'Location TBD';
};

/**
 * Helper to determine the price label.
 * @param {object} ticketInfo - The ticket info object.
 * @returns {string} The price label.
 */
const getPriceLabel = (pricing) => {
    if (!pricing) return 'Price TBD';
    if (typeof pricing === 'string') return pricing;
    if (Array.isArray(pricing)) {
        const prices = pricing
            .map(option => Number(option?.price ?? 0))
            .filter(price => Number.isFinite(price));
        if (!prices.length || prices.every(price => price <= 0)) return 'Free';
        const min = Math.min(...prices);
        const max = Math.max(...prices);
        if (min === max) return `$${min}`;
        return `$${min} - $${max}`;
    }
    return 'Price TBD';
};

/**
 * A React component to display a list of events using data and Lucide icons.
 * @param {object} props
 * @param {Array<object>} props.events - The array of event objects.
 * @param {Function} props.onBookmark - Callback for bookmarking.
 * @returns {JSX.Element}
 */
const EventCard = ({ events, onBookmark, onViewEvent, isSearching, viewMode }) => {
  // Sort and group events
  const groupEventsByDate = (eventList) => {
    // First, filter out invalid events
    const validEvents = eventList.filter(item => {
        const date = item.start_at;
        return date;
    });

    // If viewMode is 'list', OR (legacy/fallback) if searching and no viewMode override provided, return flat list
    // Ideally viewMode should be explicit: 'grid' (stacked) or 'list' (flat)
    const shouldUseFlatList = viewMode === 'list';

    if (shouldUseFlatList) {
        // If it's a flat list, we should ensure it's sorted by relevance (cosine_distance)
        // The backend already sorts by relevance if searching.
        // If not searching, backend sorts by date.
        // Ideally, if "List view", we might want to sort by distance?
        // But let's trust the backend sort order for now, or re-sort if needed.
        return validEvents.sort((a, b) => {
             // Handle nullable distance (treat None/null as infinity so they go last)
             const distA = (a.cosine_distance !== undefined && a.cosine_distance !== null) ? a.cosine_distance : Infinity;
             const distB = (b.cosine_distance !== undefined && b.cosine_distance !== null) ? b.cosine_distance : Infinity;
             return distA - distB;
        });
    }

    // Grouping for Stacked View
    const groups = {};
    validEvents.forEach(item => {
        const rawDate = item.start_at;
        const dateKey = format(new Date(rawDate), 'yyyy-MM-dd');
        if (!groups[dateKey]) groups[dateKey] = [];
        groups[dateKey].push(item);
    });

    // Sort within groups
    Object.keys(groups).forEach(key => {
        groups[key].sort((a, b) => {
             // Handle nullable distance (treat None/null as infinity so they go last)
             const distA = (a.cosine_distance !== undefined && a.cosine_distance !== null) ? a.cosine_distance : Infinity;
             const distB = (b.cosine_distance !== undefined && b.cosine_distance !== null) ? b.cosine_distance : Infinity;
             return distA - distB;
        });
    });

    // Sort groups by date
    const sortedDates = Object.keys(groups).sort();
    
    // Flatten back to a list of "Display Items"
    // Each item is either a single event or an array of events (Stack)
    const displayItems = [];
    sortedDates.forEach(date => {
        const dayEvents = groups[date];
        if (dayEvents.length === 1) {
            displayItems.push(dayEvents[0]);
        } else {
            // Push the whole array as a "Stack" item
            displayItems.push({ type: 'stack', events: dayEvents, date });
        }
    });

    return displayItems;
  };

  const displayItems = groupEventsByDate(events);

  return (
    <div className="space-y-6">
      <h2 className="text-3xl font-bold text-gray-900 border-b pb-2">Upcoming Events</h2>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {displayItems.map((item, index) => {
          if (item.type === 'stack') {
             return <EventStack key={`stack-${item.date}`} events={item.events} onBookmark={onBookmark} onViewEvent={onViewEvent} isSearching={isSearching} />;
          } else {
             return <SingleEventCard key={item.id || index} item={item} onBookmark={onBookmark} onViewEvent={onViewEvent} isSearching={isSearching} />;
          }
        })}
      </div>
    </div>
  );
};

const EventStack = ({ events, onBookmark, onViewEvent, isSearching }) => {
    const [currentIndex, setCurrentIndex] = useState(0);
    const item = events[currentIndex];
    const total = events.length;

    const handleNext = (e) => {
        e.preventDefault();
        e.stopPropagation();
        setCurrentIndex((prev) => (prev + 1) % total);
    };

    const handlePrev = (e) => {
        e.preventDefault();
        e.stopPropagation();
        setCurrentIndex((prev) => (prev - 1 + total) % total);
    };

    return (
        <div className="relative group h-full">
            {/* Background "stacked" cards effect */}
            {total > 1 && (
                <>
                    <div className="absolute top-2 left-2 right-2 bottom-0 bg-gray-200 rounded-xl transform translate-y-2 -z-10 border border-gray-300"></div>
                    <div className="absolute top-4 left-4 right-4 bottom-0 bg-gray-100 rounded-xl transform translate-y-4 -z-20 border border-gray-200"></div>
                </>
            )}

            <div className="relative bg-white shadow-lg rounded-xl overflow-hidden border border-gray-200 hover:shadow-xl transition-all duration-300 flex flex-col h-full z-0">
                {/* Stack Navigation Header */}
                <div className="bg-indigo-50 px-4 py-2 flex justify-between items-center text-xs font-medium text-indigo-700 border-b border-indigo-100">
                    <div className="flex items-center space-x-1">
                        <Layers className="w-3 h-3" />
                        <span>{currentIndex + 1} of {total} events on this day</span>
                    </div>
                    {total > 1 && (
                        <div className="flex space-x-1">
                            <button 
                                onClick={handlePrev}
                                className="flex items-center justify-center hover:bg-indigo-100 px-2 py-1 rounded transition-colors"
                                title="Previous event"
                            >
                                <ChevronLeft className="w-3 h-3" />
                            </button>
                            <button 
                                onClick={handleNext}
                                className="flex items-center justify-center hover:bg-indigo-100 px-2 py-1 rounded transition-colors"
                                title="Next event"
                            >
                                <ChevronRight className="w-3 h-3" />
                            </button>
                        </div>
                    )}
                </div>

                <SingleEventCardContent item={item} onBookmark={onBookmark} onViewEvent={onViewEvent} isSearching={isSearching} />
            </div>
        </div>
    );
};

const SingleEventCard = ({ item, onBookmark, onViewEvent, isSearching }) => {
    return (
        <div className="bg-white shadow-lg rounded-xl overflow-hidden border border-gray-200 hover:shadow-xl transition-shadow duration-300 flex flex-col relative h-full">
            <SingleEventCardContent item={item} onBookmark={onBookmark} onViewEvent={onViewEvent} isSearching={isSearching} />
        </div>
    );
};

const SingleEventCardContent = ({ item, onBookmark, onViewEvent, isSearching }) => {
    const event = item;
    const isBookmarked = item.bookmarked || false;

    // Combined Date & Time Display
    const dateTimeDisplay = formatDateTimeRange(event.start_at, event.end_at);
    
    const location = getLocation(event);
    const priceLabel = getPriceLabel(event.pricing);
    const topicLabel = (event.topic_label && event.topic_label !== 'nan' && event.topic_label !== 'nan' && event.topic_label !== 'none') ? event.topic_label : 'Unclustered';
    const topicColor = (event.topic_color && event.topic_color !== 'nan' && event.topic_color !== 'none') ? event.topic_color : '#64748B';

    // Handle URL: if it doesn't start with http, assume it's a Luma slug
    const rawUrl = event.url || '';
    const eventUrl = rawUrl.startsWith('http') ? rawUrl : `https://lu.ma/${rawUrl}`;
    const isLumaEvent = eventUrl.includes('lu.ma') || eventUrl.includes('luma.com');

    // Similarity Score / Distance
    const rawDistance = item.cosine_distance;
    const hasDistance = rawDistance !== undefined && rawDistance !== null;
    
    // Format distance for display
    const formattedDistance = hasDistance ? rawDistance.toFixed(3) : null;

    return (
        <div className="relative h-full flex flex-col p-5">
            {/* Top Right Actions: Match Score + Bookmark + Price */}
            <div className="absolute top-4 right-4 z-10 flex flex-col items-end gap-1">
                <div className="flex items-center gap-2">
                    {formattedDistance !== null && (
                        <div className={`text-xs font-bold text-white px-2 py-1 rounded-md shadow-sm ${
                            // Color coding based on raw distance
                            // < 0.2 (Very Close): Emerald
                            // < 0.35 (Close): Blue
                            // < 0.5 (Moderate): Indigo
                            // >= 0.5 (Far): Gray
                            rawDistance < 0.2 ? 'bg-gradient-to-r from-emerald-500 to-green-500' :
                            rawDistance < 0.35 ? 'bg-gradient-to-r from-blue-500 to-cyan-500' :
                            rawDistance < 0.5 ? 'bg-gradient-to-r from-indigo-500 to-purple-500' :
                            'bg-gradient-to-r from-gray-500 to-gray-600'
                        }`}>
                            Dist: {formattedDistance}
                        </div>
                    )}
                    
                    <button 
                    onClick={(e) => {
                        e.preventDefault();
                        onBookmark(item.id, !isBookmarked);
                    }}
                    className="p-1.5 rounded-full bg-white/80 hover:bg-white shadow-sm border border-gray-100 transition-colors"
                    title={isBookmarked ? "Remove bookmark" : "Bookmark event"}
                    >
                    <Bookmark className={`w-4 h-4 ${isBookmarked ? 'fill-yellow-400 text-yellow-400' : 'text-gray-400'}`} />
                    </button>
                </div>
                
                {/* Price Label (No Icon) */}
                <div className={`text-xs font-medium px-2 py-0.5 rounded-full bg-gray-100 border border-gray-200 ${priceLabel === 'Free' ? 'text-green-700' : 'text-purple-700'}`}>
                    {priceLabel}
                </div>
            </div>

            {/* Event Header - Title */}
            <div className="mb-3 pr-20">
                <h3 className="text-lg font-semibold text-gray-900 line-clamp-2 leading-tight">
                    {event.name || 'Untitled Event'}
                </h3>
            </div>

            {/* Event Details Grid */}
            <div className="grid grid-cols-1 gap-y-2 text-sm text-gray-600 mb-4">
                
                {/* Date & Time Combined */}
                <div className="flex items-center space-x-2">
                    <Calendar className="w-4 h-4 text-indigo-500 flex-shrink-0" />
                    <span className="font-medium text-gray-900">{dateTimeDisplay}</span>
                </div>

                {/* Location */}
                <div className="flex items-start space-x-2">
                    <MapPin className="w-4 h-4 text-red-500 flex-shrink-0 mt-0.5" />
                    <div className="flex flex-col overflow-hidden">
                        <span className="truncate">{location}</span>
                        {item.distance_info && (
                        <span className="text-xs text-gray-500">
                            {item.distance_info.distance_text} • {item.distance_info.duration_text} drive
                        </span>
                        )}
                    </div>
                </div>

            </div>

            {/* Tags */}
            <div className="flex flex-wrap gap-2 mb-4">
                                <div
                                    className="flex items-center space-x-1 text-xs font-medium rounded-full py-0.5 px-2.5"
                                    style={{
                                        color: topicColor,
                                        border: `1px solid ${topicColor}33`,
                                        backgroundColor: `${topicColor}14`
                                    }}
                                >
                    <Tag className="w-3 h-3" />
                                        <span>{topicLabel}</span>
                </div>
            </div>
            
            {/* Event Description (Truncated) */}
                        <Description text={event.description} color={topicColor} />

            {/* Action Button */}
            <a 
                href={eventUrl} 
                target="_blank" 
                rel="noopener noreferrer" 
                onClick={(e) => {
                    // Trigger popup (does not prevent default, so link still opens)
                    if (onViewEvent) onViewEvent(item);
                }}
                className={`mt-auto inline-flex items-center justify-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white focus:outline-none focus:ring-2 focus:ring-offset-2 transition duration-150 w-full ${
                isLumaEvent
                    ? 'bg-indigo-600 hover:bg-indigo-700 focus:ring-indigo-500'
                    : 'bg-orange-600 hover:bg-orange-700 focus:ring-orange-500'
                }`}
            >
                {isLumaEvent ? 'View on Luma' : 'View External Event'}
            </a>
            </div>
    );
}

export default EventCard;