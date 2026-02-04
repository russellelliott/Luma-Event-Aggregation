import React, { useState, useEffect } from 'react';
import { Home, Plus } from 'lucide-react';
import DistanceSlider from './components/DistanceSlider';
import ClassificationFilter from './components/ClassificationFilter';
import MultiDayCalendar from './components/MultiDayCalendar';
import DayPicker from './components/DayPicker';
import EventCard from './components/EventCard';
import AddEvent from './components/AddEvent';
import './App.css';

function App() {
  const [cities, setCities] = useState([]);
  const [selectedCityIndex, setSelectedCityIndex] = useState(0);
  const [selectedFilters, setSelectedFilters] = useState({
    eventTypes: [],
    audienceCategories: [],
    bookmarked: false
  });
  const [selectedDates, setSelectedDates] = useState([]);
  const [selectedDays, setSelectedDays] = useState(new Set());
  const [fetchedEvents, setFetchedEvents] = useState([]);
  const [view, setView] = useState('home');

  useEffect(() => {
    fetch('http://localhost:8001/cities')
      .then(res => res.json())
      .then(data => {
        setCities(data);
      })
      .catch(err => console.error('Error fetching cities:', err));
  }, []);

  useEffect(() => {
    if (cities.length === 0) return;

    const params = new URLSearchParams();
    
    // Add locations
    if (selectedCityIndex < cities.length) {
      const includedCities = cities.slice(0, selectedCityIndex + 1).map(c => c.city.split(',')[0]);
      includedCities.forEach(city => params.append('location', city));
    }

    // Add event types
    selectedFilters.eventTypes.forEach(type => params.append('event-type', type));

    // Add audience
    selectedFilters.audienceCategories.forEach(audience => params.append('audience', audience));

    // Add bookmarked
    if (selectedFilters.bookmarked) {
      params.append('bookmarked', 'true');
    }

    // Note: Dates and weekdays filtering is now done client-side to allow
    // the calendar to show event counts for all days.

    fetch(`http://localhost:8001/events?${params.toString()}`)
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data)) {
          setFetchedEvents(data);
        } else {
          console.error("Received non-array data:", data);
          setFetchedEvents([]);
        }
      })
      .catch(err => console.error('Error fetching events:', err));

  }, [cities, selectedCityIndex, selectedFilters]);

  // Filter events client-side based on Date/Weekday selection
  const visibleEvents = React.useMemo(() => {
      if (selectedDates.length === 0 && selectedDays.size === 0) {
          return fetchedEvents;
      }
      return fetchedEvents.filter(item => {
          const event = item.event || item;
          if (!event.start_at) return false;
          
          const d = new Date(event.start_at);
          
          // Check specific dates
          const dateMatch = selectedDates.some(sd => 
              sd.getFullYear() === d.getFullYear() &&
              sd.getMonth() === d.getMonth() &&
              sd.getDate() === d.getDate()
          );

          if (dateMatch) return true;

          // Check weekdays
          // 'Mon', 'Tue' -> 'mon', 'tue'
          const dayName = d.toLocaleDateString('en-US', { weekday: 'short' }).toLowerCase();
          if (selectedDays.has(dayName)) return true;
          
          return false;
      });
  }, [fetchedEvents, selectedDates, selectedDays]);

  const handleFilterChange = (category, values) => {
    setSelectedFilters(prev => ({
      ...prev,
      [category]: values
    }));
  };

  const handleBookmark = (id, isBookmarked) => {
    // Optimistic update for home list
    setFetchedEvents(prevEvents => {
      const updated = prevEvents.map(event => 
        event.id === id ? { ...event, bookmarked: isBookmarked } : event
      );
      // Remove from list if viewing bookmarks only and unbookmarking
      if (selectedFilters.bookmarked && !isBookmarked) {
        return updated.filter(e => e.id !== id);
      }
      return updated;
    });

    fetch(`http://localhost:8001/events/${id}/bookmark?bookmarked=${isBookmarked}`, {
      method: 'POST'
    })
    .then(res => res.json())
    .then(data => {
      if (data.error) {
        console.error('Error bookmarking event:', data.error);
        // Revert on error
        setFetchedEvents(prevEvents => prevEvents.map(event => 
          event.id === id ? { ...event, bookmarked: !isBookmarked } : event
        ));
      }
    })
    .catch(err => {
      console.error('Error bookmarking event:', err);
      // Revert on error
      setFetchedEvents(prevEvents => prevEvents.map(event => 
        event.id === id ? { ...event, bookmarked: !isBookmarked } : event
      ));
    });
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-50">
      <div className="container mx-auto px-4 py-8">
        <header className="mb-8 relative flex items-center justify-center">
          <button 
            onClick={() => setView('home')}
            className={`absolute left-0 p-3 rounded-full transition-colors ${
              view === 'home' 
                ? 'bg-blue-600 text-white shadow-md' 
                : 'bg-white text-gray-600 hover:bg-gray-50 border border-gray-200'
            }`}
            aria-label="Home"
          >
            <Home className="w-5 h-5" />
          </button>

          <h1 className="text-3xl font-bold text-gray-900">Luma Event Aggregation</h1>
          
          <button 
            onClick={() => setView('add-event')}
            className={`absolute right-0 p-3 rounded-full transition-colors ${
              view === 'add-event' 
                ? 'bg-blue-600 text-white shadow-md' 
                : 'bg-white text-blue-600 hover:bg-gray-50 border border-gray-200'
            }`}
            aria-label="Add Event"
          >
            <Plus className="w-5 h-5" />
          </button>
        </header>

        {view === 'home' && (
          <>
            <DistanceSlider 
              cities={cities}
              selectedCityIndex={selectedCityIndex}
              onCityChange={setSelectedCityIndex}
              eventsCount={visibleEvents.length}
            />

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
              {/* Sidebar - Filters */}
              <div className="lg:col-span-4 space-y-6">
                <ClassificationFilter 
                  selectedFilters={selectedFilters}
                  onFilterChange={handleFilterChange}
                />
                <DayPicker 
                  selectedDays={selectedDays}
                  onDaysChange={setSelectedDays}
                />
              </div>
              
              {/* Main Content - Calendar */}
              <div className="lg:col-span-8">
                <MultiDayCalendar 
                  selectedDates={selectedDates}
                  onDatesChange={setSelectedDates}
                  events={fetchedEvents}
                />
              </div>
            </div>

            <div className="mt-12">
              <EventCard events={visibleEvents} onBookmark={handleBookmark} />
            </div>
          </>
        )}

        {view === 'add-event' && (
          <AddEvent 
            onEventAdded={(newEvent) => {
              // If we are currently showing a list that should include this event, append it
              // But simplest is to just switch view and let fetch happen or just append
              setFetchedEvents(prev => [...prev, newEvent]);
              setView('home');
            }}
            onCancel={() => setView('home')}
          />
        )}
      </div>
    </div>
  );
}

export default App;