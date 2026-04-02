import React, { useState, useEffect } from 'react';
import { Home, Plus, X, Loader, LayoutList, Layers } from 'lucide-react';
import DistanceSlider from './components/DistanceSlider';
import ClassificationFilter from './components/ClassificationFilter';
import MultiDayCalendar from './components/MultiDayCalendar';
import DayPicker from './components/DayPicker';
import EventCard from './components/EventCard';
import AddEvent from './components/AddEvent';
import SearchBar from './components/SearchBar';
import MatchSlider from './components/MatchSlider';
import './App.css';

// Simple Modal Component
const Modal = ({ isOpen, onClose, title, children }) => {
  if (!isOpen) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm transition-opacity">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md overflow-hidden transform transition-all">
        <div className="flex justify-between items-center p-4 border-b">
          <h3 className="font-semibold text-gray-900">{title}</h3>
          <button onClick={onClose} className="p-1 hover:bg-gray-100 rounded-full">
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>
        <div className="p-6">
          {children}
        </div>
      </div>
    </div>
  );
};

function App() {
  const [cities, setCities] = useState([]);
  const [selectedCityIndex, setSelectedCityIndex] = useState(0);
  const [selectedFilters, setSelectedFilters] = useState({
    topicLabels: [],
    bookmarked: false,
    showPaid: false // Default: Do not show paid events
  });
  const [topicOptions, setTopicOptions] = useState([]);
  const [selectedDates, setSelectedDates] = useState([]);
  const [selectedDays, setSelectedDays] = useState(new Set());
  const [allEvents, setAllEvents] = useState([]);
  const [filteredEvents, setFilteredEvents] = useState([]);
  const [view, setView] = useState('home');
  const [isLoading, setIsLoading] = useState(false);
  
  // View Mode: 'stacked' (grouped by day) or 'list' (flat list sorted by relevance)
  const [viewMode, setViewMode] = useState('stacked');

  // Search and Match Slider State
  const [searchQuery, setSearchQuery] = useState('');
  const [maxDistanceFilter, setMaxDistanceFilter] = useState(0.8);
  const [distanceRange, setDistanceRange] = useState({ min: 0.0, max: 0.8 });
  
  // Bookmark Modal State
  const [bookmarkModalOpen, setBookmarkModalOpen] = useState(false);
  const [pendingBookmarkEventId, setPendingBookmarkEventId] = useState(null);

  // Effect to switch view mode based on search status
  useEffect(() => {
    if (searchQuery) {
      setViewMode('list');
    } else {
      setViewMode('stacked');
    }
  }, [searchQuery]);

  useEffect(() => {
    fetch('http://localhost:8001/cities')
      .then(res => res.json())
      .then(data => {
        setCities(data);
      })
      .catch(err => console.error('Error fetching cities:', err));

    fetch('http://localhost:8001/topics')
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data)) {
          setTopicOptions(data);
        }
      })
      .catch(err => console.error('Error fetching topics:', err));
  }, []);

  // Fetch all events once or when non-distance filters change
  useEffect(() => {
    const params = new URLSearchParams();
    
    // Add topics
    selectedFilters.topicLabels.forEach(topic => params.append('topic', topic));

    // Add bookmarked
    if (selectedFilters.bookmarked) {
      params.append('bookmarked', 'true');
    }
    
    // Add search query
    if (searchQuery) {
      params.append('query', searchQuery);
    }

    setIsLoading(true);
    fetch(`http://localhost:8001/events/all?${params.toString()}`)
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data)) {
          setAllEvents(data);
          
          // Calculate distance range on load/search
          const distances = data.map(e => e.cosine_distance).filter(d => d !== undefined && d !== null);
          
          if (distances.length > 0) {
            const min = Math.min(...distances);
            const max = Math.max(...distances);
            const minRounded = Math.floor(min * 100) / 100;
            const maxRounded = Math.ceil((max + 0.05) * 100) / 100;
            
            setDistanceRange({ min: minRounded, max: maxRounded });
            
            // Set slider to max available distance initially so all events match
            setMaxDistanceFilter(maxRounded);
          } else {
             setDistanceRange({ min: 0.0, max: 2.0 });
             setMaxDistanceFilter(2.0);
          }
        } else {
          console.error("Received non-array data:", data);
          setAllEvents([]);
        }
      })
      .catch(err => console.error('Error fetching events:', err))
      .finally(() => setIsLoading(false));

  }, [selectedFilters.topicLabels, selectedFilters.bookmarked, searchQuery]); // Exclude selectedFilters.showPaid from fetch dep, handle on client

  // Filter events client-side
  useEffect(() => {
    if (cities.length === 0 || allEvents.length === 0) {
      setFilteredEvents([]);
      return;
    }

    // Get max distance from current slider position
    const cityIndex = Math.min(selectedCityIndex, cities.length - 1);
    const citiesUpToSlider = cities.slice(0, cityIndex + 1);
    const maxDistance = Math.max(...citiesUpToSlider.map(c => c.distance_miles || 0));

    const filtered = allEvents.filter(event => {
      // 1. Distance Filter
      const distanceInfo = event.distance_info;
      let validDistance = false;
      if (distanceInfo && typeof distanceInfo.distance_miles === 'number') {
        validDistance = distanceInfo.distance_miles <= maxDistance;
      } else {
        validDistance = false;
      }
      if (!validDistance) return false;

      // 2. Paid/Free Filter
      // If showPaid is false, ONLY show Free events
      if (!selectedFilters.showPaid) {
        const pricing = event.pricing;
        const pricingText = typeof pricing === 'string' ? pricing.toLowerCase() : '';
        if (pricingText && pricingText.includes('paid')) return false;
        if (Array.isArray(pricing)) {
          const hasPaidOption = pricing.some(option => {
            const value = Number(option?.price ?? 0);
            return Number.isFinite(value) && value > 0;
          });
          if (hasPaidOption) return false;
        }
      }
      
      // 3. Match Distance Filter (Cosine Distance)
      const distance = event.cosine_distance;
      // Filter out events that exceed max distance if set < 1.0 (or default max)
      if (distance !== undefined && distance !== null) {
          if (distance > maxDistanceFilter) return false;
      }

      return true;
    });
    
    setFilteredEvents(filtered);
  }, [allEvents, selectedCityIndex, cities, selectedFilters.showPaid, maxDistanceFilter]);

  // Filter events client-side based on Date/Weekday selection
  const visibleEvents = React.useMemo(() => {
      if (selectedDates.length === 0 && selectedDays.size === 0) {
          return filteredEvents;
      }
      return filteredEvents.filter(item => {
          if (!item.start_at) return false;
          
          const d = new Date(item.start_at);
          
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
  }, [filteredEvents, selectedDates, selectedDays]);

  const handleFilterChange = (category, values) => {
    setSelectedFilters(prev => ({
      ...prev,
      [category]: values
    }));
  };

  const bookmarkEvent = (id, isBookmarked) => {
    // Optimistic update for home list
    setAllEvents(prevEvents => {
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
        setAllEvents(prevEvents => prevEvents.map(event => 
          event.id === id ? { ...event, bookmarked: !isBookmarked } : event
        ));
      }
    })
    .catch(err => {
      console.error('Error bookmarking event:', err);
      // Revert on error
      setAllEvents(prevEvents => prevEvents.map(event => 
        event.id === id ? { ...event, bookmarked: !isBookmarked } : event
      ));
    });
  };

  const handleBookmark = (id, isBookmarked) => {
    bookmarkEvent(id, isBookmarked);
  };
  
  const handleViewEvent = (event) => {
      if (!event.bookmarked) {
          setPendingBookmarkEventId(event.id);
          setBookmarkModalOpen(true);
      }
  };

  const confirmBookmark = () => {
      if (pendingBookmarkEventId) {
          bookmarkEvent(pendingBookmarkEventId, true);
      }
      setBookmarkModalOpen(false);
      setPendingBookmarkEventId(null);
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
            <div className="mb-6 flex flex-col md:flex-row gap-4 justify-center items-center">
                <SearchBar onSearch={setSearchQuery} />
                
                {/* View Toggle */}
                <div className="flex bg-white rounded-lg shadow-sm border border-gray-200 p-1">
                    <button
                        onClick={() => setViewMode('stacked')}
                        className={`p-2 rounded-md transition-colors ${
                            viewMode === 'stacked' 
                                ? 'bg-indigo-100 text-indigo-700' 
                                : 'text-gray-500 hover:bg-gray-50'
                        }`}
                        title="Group by Date"
                    >
                        <Layers className="w-5 h-5" />
                    </button>
                    <button
                        onClick={() => setViewMode('list')}
                        className={`p-2 rounded-md transition-colors ${
                            viewMode === 'list' 
                                ? 'bg-indigo-100 text-indigo-700' 
                                : 'text-gray-500 hover:bg-gray-50'
                        }`}
                        title="List by Relevance"
                    >
                        <LayoutList className="w-5 h-5" />
                    </button>
                </div>
            </div>

            <DistanceSlider 
              cities={cities}
              selectedCityIndex={selectedCityIndex}
              onCityChange={setSelectedCityIndex}
              eventsCount={visibleEvents.length}
            />

            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
              {/* Sidebar - Filters */}
              <div className="lg:col-span-8">
                 <MultiDayCalendar 
                  selectedDates={selectedDates}
                  onDatesChange={setSelectedDates}
                  events={filteredEvents}
                />
              </div>
              
              {/* Event Classifications */}
              <div className="lg:col-span-4 space-y-4">
                <ClassificationFilter 
                  selectedFilters={selectedFilters}
                  onFilterChange={handleFilterChange}
                  topicOptions={topicOptions}
                />
                
                <MatchSlider 
                    maxDistance={maxDistanceFilter} 
                    setMaxDistance={setMaxDistanceFilter} 
                    range={distanceRange}
                />
                
                <DayPicker 
                  selectedDays={selectedDays}
                  onDaysChange={setSelectedDays}
                />
              </div>
            </div>

            <div className="mt-12">
              {isLoading ? (
                  <div className="flex justify-center items-center h-64">
                    <Loader className="w-12 h-12 animate-spin text-indigo-600" />
                  </div>
              ) : (
                  <EventCard 
                    events={visibleEvents} 
                    onBookmark={handleBookmark} 
                    onViewEvent={handleViewEvent}
                    isSearching={!!searchQuery} // Pass search state
                    viewMode={viewMode}
                  />
              )}
            </div>
          </>
        )}

        {view === 'add-event' && (
          <AddEvent 
            onEventAdded={(newEvent) => {
              setAllEvents(prev => [...prev, newEvent]);
              setView('home');
            }}
            onCancel={() => setView('home')}
          />
        )}
        
        {/* Bookmark Prompt Modal */}
        <Modal 
            isOpen={bookmarkModalOpen} 
            onClose={() => setBookmarkModalOpen(false)}
            title="Bookmark this event?"
        >
            <p className="text-gray-600 mb-6">
                You just viewed this event on Luma. Would you like to add it to your bookmarks for easier access later?
            </p>
            <div className="flex justify-end gap-3">
                <button 
                    onClick={() => setBookmarkModalOpen(false)}
                    className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg text-sm font-medium transition-colors"
                >
                    No thanks
                </button>
                <button 
                    onClick={confirmBookmark}
                    className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 transition-colors shadow-sm"
                >
                    Yes, Bookmark
                </button>
            </div>
        </Modal>
      </div>
    </div>
  );
}

export default App;