import React, { useState, useEffect } from 'react';
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
    audienceCategories: []
  });
  const [selectedDates, setSelectedDates] = useState([]);
  const [selectedDays, setSelectedDays] = useState(new Set());
  const [events, setEvents] = useState([]);
  const [view, setView] = useState('home');
  const [bookmarkedEvents, setBookmarkedEvents] = useState([]);

  useEffect(() => {
    fetch('http://localhost:8000/cities')
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
    const includedCities = cities.slice(0, selectedCityIndex + 1).map(c => c.city.split(',')[0]);
    includedCities.forEach(city => params.append('location', city));

    // Add event types
    selectedFilters.eventTypes.forEach(type => params.append('event-type', type));

    // Add audience
    selectedFilters.audienceCategories.forEach(audience => params.append('audience', audience));

    // Add dates
    selectedDates.forEach(date => params.append('dates', date.toISOString().split('T')[0]));

    // Add weekdays
    const weekdayMap = {
      'mon': 'Monday',
      'tue': 'Tuesday',
      'wed': 'Wednesday',
      'thu': 'Thursday',
      'fri': 'Friday',
      'sat': 'Saturday',
      'sun': 'Sunday'
    };
    Array.from(selectedDays).forEach(day => {
      if (weekdayMap[day]) {
        params.append('weekdays', weekdayMap[day]);
      }
    });

    fetch(`http://localhost:8000/events?${params.toString()}`)
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data)) {
          setEvents(data);
        } else {
          console.error("Received non-array data:", data);
          setEvents([]);
        }
      })
      .catch(err => console.error('Error fetching events:', err));

  }, [cities, selectedCityIndex, selectedFilters, selectedDates, selectedDays]);

  useEffect(() => {
    if (view === 'bookmarks') {
      fetch('http://localhost:8000/bookmarks')
        .then(res => res.json())
        .then(data => {
          if (Array.isArray(data)) {
            setBookmarkedEvents(data);
          } else {
            console.error("Received non-array bookmarks data:", data);
            setBookmarkedEvents([]);
          }
        })
        .catch(err => console.error('Error fetching bookmarks:', err));
    }
  }, [view]);

  const handleFilterChange = (category, values) => {
    setSelectedFilters(prev => ({
      ...prev,
      [category]: values
    }));
  };

  const handleBookmark = (id, isBookmarked) => {
    // Optimistic update for home list
    setEvents(prevEvents => prevEvents.map(event => 
      event.id === id ? { ...event, bookmarked: isBookmarked } : event
    ));

    // Optimistic update for bookmarks list
    if (view === 'bookmarks' && !isBookmarked) {
      setBookmarkedEvents(prev => prev.filter(e => e.id !== id));
    }

    fetch(`http://localhost:8000/events/${id}/bookmark?bookmarked=${isBookmarked}`, {
      method: 'POST'
    })
    .then(res => res.json())
    .then(data => {
      if (data.error) {
        console.error('Error bookmarking event:', data.error);
        // Revert on error
        setEvents(prevEvents => prevEvents.map(event => 
          event.id === id ? { ...event, bookmarked: !isBookmarked } : event
        ));
        // Re-fetch bookmarks to restore state if needed
        if (view === 'bookmarks') {
          fetch('http://localhost:8000/bookmarks')
            .then(res => res.json())
            .then(data => setBookmarkedEvents(data || []));
        }
      }
    })
    .catch(err => {
      console.error('Error bookmarking event:', err);
      // Revert on error
      setEvents(prevEvents => prevEvents.map(event => 
        event.id === id ? { ...event, bookmarked: !isBookmarked } : event
      ));
      if (view === 'bookmarks') {
        fetch('http://localhost:8000/bookmarks')
          .then(res => res.json())
          .then(data => setBookmarkedEvents(data || []));
      }
    });
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-50">
      <div className="container mx-auto px-4 py-8">
        <header className="text-center mb-12">
          <h1 className="text-3xl font-bold text-gray-900">Luma Event Aggregation</h1>
          
          <div className="flex justify-center space-x-4 mt-6">
            <button 
              onClick={() => setView('home')}
              className={`px-6 py-2 rounded-full font-medium transition-colors ${
                view === 'home' 
                  ? 'bg-blue-600 text-white shadow-md' 
                  : 'bg-white text-gray-600 hover:bg-gray-50 border border-gray-200'
              }`}
            >
              Home
            </button>
            <button 
              onClick={() => setView('bookmarks')}
              className={`px-6 py-2 rounded-full font-medium transition-colors ${
                view === 'bookmarks' 
                  ? 'bg-blue-600 text-white shadow-md' 
                  : 'bg-white text-gray-600 hover:bg-gray-50 border border-gray-200'
              }`}
            >
              Bookmarks
            </button>
            <button 
              onClick={() => setView('add-event')}
              className={`px-6 py-2 rounded-full font-medium transition-colors ${
                view === 'add-event' 
                  ? 'bg-blue-600 text-white shadow-md' 
                  : 'bg-white text-gray-600 hover:bg-gray-50 border border-gray-200'
              }`}
            >
              Add Event
            </button>
          </div>

          {view === 'home' && (
            <>
              <p className="mt-4 text-gray-600">Find events near you</p>
              <p className="mt-2 text-blue-600 font-medium">Found {events.length} events</p>
            </>
          )}
        </header>

        {view === 'home' && (
          <>
            <DistanceSlider 
              cities={cities}
              selectedCityIndex={selectedCityIndex}
              onCityChange={setSelectedCityIndex}
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
                />
              </div>
            </div>

            <div className="mt-12">
              <EventCard events={events} onBookmark={handleBookmark} />
            </div>
          </>
        )}

        {view === 'bookmarks' && (
          <div className="max-w-7xl mx-auto">
            <h2 className="text-2xl font-bold mb-6 text-gray-900">Your Bookmarked Events</h2>
            {bookmarkedEvents.length === 0 ? (
              <div className="text-center py-12 bg-white rounded-xl border border-gray-200">
                <p className="text-gray-500">No bookmarked events yet.</p>
                <button 
                  onClick={() => setView('home')}
                  className="mt-4 text-blue-600 hover:text-blue-800 font-medium"
                >
                  Browse events
                </button>
              </div>
            ) : (
              <EventCard events={bookmarkedEvents} onBookmark={handleBookmark} />
            )}
          </div>
        )}

        {view === 'add-event' && (
          <AddEvent 
            onEventAdded={(newEvent) => {
              setEvents(prev => [...prev, newEvent]);
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