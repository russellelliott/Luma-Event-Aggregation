import React from 'react';
import { format } from 'date-fns';
import { Calendar, Clock, MapPin, Users, Ticket, Tag } from 'lucide-react';

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
 * @returns {JSX.Element}
 */
const EventCard = ({ events }) => {
  return (
    <div className="space-y-6">
      <h2 className="text-3xl font-bold text-gray-900 border-b pb-2">Upcoming Events</h2>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {events.map((item, index) => {
          // Use optional chaining and nullish coalescing for safety
          // Handle both nested and flat event structures
          const event = item.event || item;
          const ticket_info = item.ticket_info || event.ticket_info || {};
          const guest_count = item.guest_count || event.guest_count || 0;

          const startDate = new Date(event.start_at);
          const eventDate = format(startDate, 'EEEE, MMM d, yyyy');
          const eventTime = event.start_at && event.end_at 
            ? formatTimeRange(event.start_at, event.end_at) 
            : 'Time TBD';
          
          const location = getLocation(event);
          const priceLabel = getPriceLabel(ticket_info);
          const eventType = event.event_type ? event.event_type.replace(/_/g, ' ') : 'General Event';

          return (
            <div
              key={event.api_id || index}
              className="bg-white shadow-lg rounded-xl overflow-hidden border border-gray-200 hover:shadow-xl transition-shadow duration-300 flex flex-col"
            >
              <div className="p-5 flex-1 flex flex-col">
                {/* Event Header */}
                <h3 className="text-xl font-semibold text-gray-900 mb-2 line-clamp-2 h-14">{event.name || 'Untitled Event'}</h3>

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
                  <div className="flex items-center space-x-2">
                    <MapPin className="w-4 h-4 text-red-500 flex-shrink-0" />
                    <span className="truncate">{location}</span>
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

                {/* Event Type / Tag */}
                <div className="flex items-center space-x-2 text-xs font-medium text-indigo-700 bg-indigo-100 rounded-full py-1 px-3 w-fit mb-4">
                    <Tag className="w-3 h-3" />
                    <span className="uppercase">{eventType}</span>
                </div>
                
                {/* Event Description (Truncated) */}
                <p className="text-gray-700 line-clamp-3 mb-4 flex-1">
                  {event.description || 'No description provided.'}
                </p>

                {/* Action Button */}
                <a 
                  href={`https://luma.com/${event.url}`} 
                  target="_blank" 
                  rel="noopener noreferrer" 
                  className="mt-auto inline-flex items-center justify-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 transition duration-150 w-full"
                >
                  View Details
                </a>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default EventCard;