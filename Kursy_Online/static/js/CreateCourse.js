const CreateCourse = () => {
  const [formData, setFormData] = React.useState({
    title: '',
    description: '',
    price: 0,
    level: 'BEGINNER',
    technologies: [],
    coverImage: null,
    isPublished: false
  });

  const [message, setMessage] = React.useState({ type: '', text: '' });
  const [loading, setLoading] = React.useState(false);

  const handleInputChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
  };

  const handleImageChange = (e) => {
    const file = e.target.files[0];
    setFormData(prev => ({
      ...prev,
      coverImage: file
    }));
  };

  const handleTechnologiesChange = (e) => {
    const options = e.target.options;
    const selected = [];
    for (let i = 0; i < options.length; i++) {
      if (options[i].selected) {
        selected.push(options[i].value);
      }
    }
    setFormData(prev => ({
      ...prev,
      technologies: selected
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const formDataToSend = new FormData();
      Object.keys(formData).forEach(key => {
        if (key === 'technologies') {
          formData[key].forEach(tech => {
            formDataToSend.append('technologies', tech);
          });
        } else if (key === 'coverImage' && formData[key]) {
          formDataToSend.append('cover_image', formData[key]);
        } else {
          formDataToSend.append(key, formData[key]);
        }
      });

      const response = await fetch('/api/courses/', {
        method: 'POST',
        body: formDataToSend,
        credentials: 'include'
      });

      if (!response.ok) {
        throw new Error('Failed to create course');
      }

      setMessage({ type: 'success', text: 'Course created successfully!' });
      setFormData({
        title: '',
        description: '',
        price: 0,
        level: 'BEGINNER',
        technologies: [],
        coverImage: null,
        isPublished: false
      });
    } catch (error) {
      setMessage({ type: 'error', text: error.message });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto p-6">
      <h1 className="text-2xl font-bold mb-6">Create New Course</h1>
      
      {message.text && (
        <div className={`mb-4 p-4 rounded ${message.type === 'error' ? 'bg-red-100' : 'bg-green-100'}`}>
          {message.text}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-2">
          <label className="block text-sm font-medium">Title</label>
          <input
            type="text"
            name="title"
            value={formData.title}
            onChange={handleInputChange}
            required
            className="w-100 form-control"
          />
        </div>

        <div className="space-y-2">
          <label className="block text-sm font-medium">Description</label>
          <textarea
            name="description"
            value={formData.description}
            onChange={handleInputChange}
            required
            rows="4"
            className="w-100 form-control"
          />
        </div>

        <div className="space-y-2">
          <label className="block text-sm font-medium">Price</label>
          <input
            type="number"
            name="price"
            value={formData.price}
            onChange={handleInputChange}
            required
            min="0"
            step="0.01"
            className="w-100 form-control"
          />
        </div>

        <div className="space-y-2">
          <label className="block text-sm font-medium">Level</label>
          <select
            name="level"
            value={formData.level}
            onChange={handleInputChange}
            required
            className="w-100 form-control"
          >
            <option value="BEGINNER">Beginner</option>
            <option value="INTERMEDIATE">Intermediate</option>
            <option value="ADVANCED">Advanced</option>
          </select>
        </div>

        <div className="space-y-2">
          <label className="block text-sm font-medium">Technologies</label>
          <select
            multiple
            name="technologies"
            value={formData.technologies}
            onChange={handleTechnologiesChange}
            className="w-100 form-control"
          >
            <option value="python">Python</option>
            <option value="javascript">JavaScript</option>
            <option value="react">React</option>
            <option value="django">Django</option>
          </select>
        </div>

        <div className="space-y-2">
          <label className="block text-sm font-medium">Cover Image</label>
          <input
            type="file"
            name="coverImage"
            onChange={handleImageChange}
            accept="image/*"
            className="w-100 form-control"
          />
        </div>

        <div className="form-check">
          <input
            type="checkbox"
            name="isPublished"
            checked={formData.isPublished}
            onChange={handleInputChange}
            className="form-check-input"
          />
          <label className="form-check-label">Publish immediately</label>
        </div>

        <button
          type="submit"
          disabled={loading}
          className={`btn btn-primary w-100 ${loading ? 'opacity-50' : ''}`}
        >
          {loading ? 'Creating...' : 'Create Course'}
        </button>
      </form>
    </div>
  );
};