import React, { useState } from 'react';
import { format } from 'date-fns';
import { Calendar, Clock, MapPin, Users, Ticket, Tag, Bookmark, Layers, ChevronRight, ChevronLeft } from 'lucide-react';

/**
 * Component to handle description truncation and expansion
 */
const Description = ({ text }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  
  if (!text) return <p className="text-gray-700 mb-4 flex-1">No description provided.</p>;

  // Heuristic: only show toggle if text is reasonably long
  const shouldTruncate = text.length > 150;

  if (!shouldTruncate) {
      return <p className="text-gray-700 mb-4 flex-1">{text}</p>;
  }

  return (
    <div className="mb-4 flex-1">
      <p className={`text-gray-700 ${isExpanded ? '' : 'line-clamp-3'}`}>
        {text}
      </p>
      <button 
        onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            setIsExpanded(!isExpanded);
        }}
        className="text-indigo-600 hover:text-indigo-800 text-sm font-medium mt-1 focus:outline-none"
      >
        {isExpanded ? 'Show less' : 'Read more'}
      </button>
    </div>
  );
};

/**
 * Helper to format the time range.
 * @param {string} start - ISO start time string.
 * @param {string} end - ISO end time string.
 * @returns {string} Formatted time range string.
 */
const formatTimeRange = (start, end) => {
  // Ensure the dates are valid before formatting
  const startDate = new Date(start);
  const endDate = new Date(end);
  
  if (isNaN(startDate) || isNaN(endDate)) {
    return 'Time TBD';
  }

  const startTime = format(startDate, 'h:mm a');
  const endTime = format(endDate, 'h:mm a');
  return `${startTime} - ${endTime}`;
};

/**
 * Helper to determine the location string.
 * @param {object} event - The event object.
 * @returns {string} The location string.
 */
const getLocation = (event) => {
  if (event.location_type === 'online') return 'Online';
  const geo = event.geo_address_info || {};
  return geo.short_address || geo.address || geo.full_address || geo.city_state || 'Location TBD';
};

/**
 * Helper to determine the price label.
 * @param {object} ticketInfo - The ticket info object.
 * @returns {string} The price label.
 */
const getPriceLabel = (ticketInfo) => {
  if (!ticketInfo) return 'Price TBD';
  
  const priceCents = ticketInfo.price?.cents || 0;
  const maxPriceCents = ticketInfo.max_price?.cents || 0;
  
  // Determine currency
  const currency = ticketInfo.price?.currency || ticketInfo.max_price?.currency || ticketInfo.currency_info?.currency || 'USD';
  // Handle empty string currency
  const validCurrency = currency === '' ? 'USD' : currency;

  if (priceCents === 0 && maxPriceCents === 0) return 'Free';

  const formatPrice = (cents) => {
      return new Intl.NumberFormat('en-US', {
          style: 'currency',
          currency: validCurrency,
          minimumFractionDigits: cents % 100 === 0 ? 0 : 2
      }).format(cents / 100);
  };

  if (priceCents === 0 && maxPriceCents > 0) {
      return `Free - ${formatPrice(maxPriceCents)}`;
  }

  if (priceCents > 0) {
      if (maxPriceCents > priceCents) {
          return `${formatPrice(priceCents)} - ${formatPrice(maxPriceCents)}`;
      }
      return formatPrice(priceCents);
  }
  
  return 'Free';
};

/**
 * A React component to display a list of events using data and Lucide icons.
 * @param {object} props
 * @param {Array<object>} props.events - The array of event objects.
 * @param {Function} props.onBookmark - Callback for bookmarking.
 * @returns {JSX.Element}
 */
const EventCard = ({ events, onBookmark }) => {
  // Sort and group events
  const groupEventsByDate = (eventList) => {
    // First, filter out invalid events
    const validEvents = eventList.filter(item => {
        const date = item.start_at || (item.event && item.event.start_at);
        return date;
    });

    // Grouping
    const groups = {};
    validEvents.forEach(item => {
        const rawDate = item.start_at || (item.event && item.event.start_at);
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
             return <EventStack key={`stack-${item.date}`} events={item.events} onBookmark={onBookmark} />;
          } else {
             return <SingleEventCard key={item.id || index} item={item} onBookmark={onBookmark} />;
          }
        })}
      </div>
    </div>
  );
};

const EventStack = ({ events, onBookmark }) => {
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

                <SingleEventCardContent item={item} onBookmark={onBookmark} />
            </div>
        </div>
    );
};

const SingleEventCard = ({ item, onBookmark }) => {
    return (
        <div className="bg-white shadow-lg rounded-xl overflow-hidden border border-gray-200 hover:shadow-xl transition-shadow duration-300 flex flex-col relative h-full">
            <SingleEventCardContent item={item} onBookmark={onBookmark} />
        </div>
    );
};

const SingleEventCardContent = ({ item, onBookmark }) => {
    // Use optional chaining and nullish coalescing for safety
    // Handle both nested and flat event structures
    const event = item.event || item;
    const ticket_info = item.ticket_info || event.ticket_info || {};
    const guest_count = item.guest_count || event.guest_count || 0;
    const isBookmarked = item.bookmarked || false;

    const startDate = new Date(event.start_at);
    const eventDate = format(startDate, 'EEEE, MMM d, yyyy');
    const eventTime = event.start_at && event.end_at 
    ? formatTimeRange(event.start_at, event.end_at) 
    : 'Time TBD';
    
    const location = getLocation(event);
    const priceLabel = getPriceLabel(ticket_info);
    const eventType = event.event_type ? event.event_type.replace(/_/g, ' ') : 'General Event';
    const audience = event.audience ? event.audience.replace(/_/g, ' ') : 'General Audience';

    // Handle URL: if it doesn't start with http, assume it's a Luma slug
    const rawUrl = event.url || '';
    const eventUrl = rawUrl.startsWith('http') ? rawUrl : `https://lu.ma/${rawUrl}`;
    const isLumaEvent = eventUrl.includes('lu.ma') || eventUrl.includes('luma.com');

    // Similarity Score / Distance
    const distance = item.cosine_distance;
    const hasDistance = distance !== undefined && distance !== null;
    // Format distance as similarity % (1 - distance) * 100
    // distance is roughly 0 (identical) to 1 (orthogonal) to 2 (opposite)
    // For practical purposes in embeddings, 0.0 is exact match.
    // Let's verify range. Cosine distance usually [0, 2].
    // Let's display "Relevance Score"
    // 1 - distance is similarity [-1, 1].
    // If distance is explicitly cosine distance [0, 2]
    // 0 -> 100% match
    
    // Let's just show "Distance: 0.12" for now or convert to a nice "Match Score"
    // Match Score = (1 - distance) * 100 might be negative if distance > 1.
    // Embeddings are usually normalized so dot product is [-1, 1].
    // Distance = 1 - dot product => [0, 2].
    // Let's scale [0, 1] distance to 100-0% score?
    // Usually semantic similarity is positive.
    
    // Let's just create a simple "AI Match" badge if distance is low enough, or show the value.
    const matchScore = hasDistance ? Math.round((1 - distance) * 100) : null;

    return (
        <>
            <button 
            onClick={(e) => {
                e.preventDefault();
                onBookmark(item.id, !isBookmarked);
            }}
            className="absolute top-10 right-2 p-2 rounded-full bg-white/80 hover:bg-white shadow-sm z-10 transition-colors"
            title={isBookmarked ? "Remove bookmark" : "Bookmark event"}
            >
            <Bookmark className={`w-5 h-5 ${isBookmarked ? 'fill-yellow-400 text-yellow-400' : 'text-gray-400'}`} />
            </button>

            <div className="p-5 flex-1 flex flex-col">
            {/* Event Header */}
            <div className="flex justify-between items-start mb-2">
                <h3 className="text-xl font-semibold text-gray-900 line-clamp-2 h-14 flex-1 pr-8">{event.name || 'Untitled Event'}</h3>
            </div>

            {hasDistance && (
                <div className="flex items-center space-x-1 mb-3">
                    <div className="text-xs font-bold text-white bg-gradient-to-r from-blue-500 to-purple-500 px-2 py-1 rounded-md shadow-sm">
                        {matchScore}% Match
                    </div>
                </div>
            )}

            {/* Event Details Grid */}
            <div className="grid grid-cols-1 gap-y-2 text-sm text-gray-600 mb-4">
                
                {/* Date */}
                <div className="flex items-center space-x-2">
                <Calendar className="w-4 h-4 text-indigo-500 flex-shrink-0" />
                <span>{eventDate}</span>
                </div>

                {/* Time */}
                <div className="flex items-center space-x-2">
                <Clock className="w-4 h-4 text-indigo-500 flex-shrink-0" />
                <span>{eventTime}</span>
                </div>

                {/* Location */}
                <div className="flex items-start space-x-2">
                <MapPin className="w-4 h-4 text-red-500 flex-shrink-0 mt-1" />
                <div className="flex flex-col overflow-hidden">
                    <span className="truncate">{location}</span>
                    {item.distance_info && (
                    <span className="text-xs text-gray-500">
                        {item.distance_info.distance_text} • {item.distance_info.duration_text} drive
                    </span>
                    )}
                </div>
                </div>

                {/* Guests */}
                <div className="flex items-center space-x-2">
                <Users className="w-4 h-4 text-green-500 flex-shrink-0" />
                <span>{guest_count} Guest{guest_count !== 1 ? 's' : ''}</span>
                </div>

                {/* Pricing (Ticket Info) */}
                <div className="flex items-center space-x-2">
                <Ticket className="w-4 h-4 text-purple-500 flex-shrink-0" />
                <span className={`font-medium ${priceLabel === 'Free' ? 'text-green-600' : 'text-purple-600'}`}>
                    {priceLabel}
                </span>
                </div>

            </div>

            {/* Tags */}
            <div className="flex flex-wrap gap-2 mb-4">
                {/* Event Type */}
                <div className="flex items-center space-x-1 text-xs font-medium text-indigo-700 bg-indigo-100 rounded-full py-1 px-3">
                    <Tag className="w-3 h-3" />
                    <span className="uppercase">{eventType}</span>
                </div>
                {/* Audience */}
                <div className="flex items-center space-x-1 text-xs font-medium text-emerald-700 bg-emerald-100 rounded-full py-1 px-3">
                    <Users className="w-3 h-3" />
                    <span className="uppercase">{audience}</span>
                </div>
            </div>
            
            {/* Event Description (Truncated) */}
            <Description text={event.description} />

            {/* Action Button */}
            <a 
                href={eventUrl} 
                target="_blank" 
                rel="noopener noreferrer" 
                className={`mt-auto inline-flex items-center justify-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white focus:outline-none focus:ring-2 focus:ring-offset-2 transition duration-150 w-full ${
                isLumaEvent
                    ? 'bg-indigo-600 hover:bg-indigo-700 focus:ring-indigo-500'
                    : 'bg-orange-600 hover:bg-orange-700 focus:ring-orange-500'
                }`}
            >
                {isLumaEvent ? 'View on Luma' : 'View External Event'}
            </a>
            </div>
        </>
    );
}

export default EventCard;