# 🚀 Data Analytics API

A powerful Flask-based API that performs intelligent data analysis using Claude AI. Upload CSV files, ask questions, and get comprehensive statistical analysis with visualizations.

## ✨ Features

- **📊 Statistical Analysis**: Calculate mean, median, mode, correlation coefficients, standard deviation, percentiles
- **📈 Data Visualizations**: Generate charts, histograms, scatter plots, network graphs as base64 PNG images
- **🌐 Web Scraping**: Analyze data from URLs (Wikipedia, websites with tables)
- **📤 File Upload**: Support for CSV data files and text question files
- **🔍 4 Question Types**:
  - **Type 1**: Direct questions (no files needed)
  - **Type 2**: Analysis with uploaded data files
  - **Type 3**: Questions requiring web research
  - **Type 4**: Web scraping with specific URLs

## 🛠️ Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/data-analytics-api.git
   cd data-analytics-api
   ```

2. **Create virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # or
   venv\Scripts\activate     # Windows
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**:
   ```bash
   # Create .env file and add your Anthropic API key
   echo "ANTHROPIC_API_KEY=your_api_key_here" > .env
   ```

5. **Run the application**:
   ```bash
   python app.py
   ```

## 🚀 Usage

### Web Interface
Visit `http://localhost:8000` to use the web interface for uploading files and asking questions.

### API Endpoints

#### POST /analyze

**Type 1 - Direct Question:**
```bash
curl -X POST "http://localhost:8000/analyze" \
  -F "question=What is the average of 1,2,3,4,5?"
```

**Type 2 - With Data Files:**
```bash
curl -X POST "http://localhost:8000/analyze" \
  -F "questions=@questions.txt" \
  -F "data=@dataset.csv"
```

**Type 3 - Web Research:**
```bash
curl -X POST "http://localhost:8000/analyze" \
  -F "question=Who won FIFA World Cup 2022?"
```

**Type 4 - URL Scraping:**
```bash
curl -X POST "http://localhost:8000/analyze" \
  -F "question=Scrape data from https://en.wikipedia.org/wiki/List_of_highest-grossing_films"
```

## 📊 Example Responses

```json
{
  "total_sales": 1140,
  "average_temp": 23.5,
  "correlation_coefficient": 0.847,
  "scatter_plot": "data:image/png;base64,iVBORw0KGgo...",
  "highest_degree_node": "Alice"
}
```

## 📁 Project Structure

```
data-analytics-api/
├── app.py              # Main Flask application
├── requirements.txt    # Python dependencies
├── .env               # Environment variables (not tracked)
├── .gitignore         # Git ignore rules
├── README.md          # Project documentation
├── uploads/           # Uploaded files directory
│   ├── questions.txt  # Sample question files
│   ├── sample-sales.csv
│   └── edges.csv
└── scripts/           # Generated analysis scripts
```

## 🔧 Configuration

### Environment Variables

- `ANTHROPIC_API_KEY`: Your Anthropic Claude API key (required)

### Supported File Types

- **Question files**: `.txt` files containing analysis questions
- **Data files**: `.csv` files with structured data
- **Generated charts**: Base64-encoded PNG images (max 4KB, 80x60 pixels)

## 🤖 AI Models Used

- **Types 1-3**: Claude-3.5-Sonnet (claude-3-5-sonnet-20241022)
- **Type 4**: Claude-3.5-Haiku (claude-3-5-haiku-20241022) for web scraping

## 🛡️ Security

- API keys stored in `.env` file (not tracked by git)
- File uploads saved to secure `uploads/` directory
- Input validation and error handling

## 📈 Performance Optimizations

- Optimized image generation (80x60 pixels, 4KB max)
- Efficient token usage (6000 tokens for complex analysis)
- Fast response times (typically under 1 minute)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make changes and test
4. Commit: `git commit -am 'Add feature'`
5. Push: `git push origin feature-name`
6. Create Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

If you encounter issues:

1. Check your API key is correctly set in `.env`
2. Ensure all dependencies are installed
3. Verify file formats (CSV for data, TXT for questions)
4. Check server logs for detailed error messages

## 🎯 Roadmap

- [ ] Add support for Excel files
- [ ] Implement caching for repeated queries
- [ ] Add user authentication
- [ ] Support for more chart types
- [ ] Batch processing for multiple files

---

**⚡ Powered by Anthropic Claude & Flask**