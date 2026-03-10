#include "utils/MatrixIO.h"

#include <algorithm>
#include <cctype>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

namespace {

std::string trim(const std::string& s) {
    size_t start = 0;
    while (start < s.size() && std::isspace(static_cast<unsigned char>(s[start]))) {
        start++;
    }
    size_t end = s.size();
    while (end > start && std::isspace(static_cast<unsigned char>(s[end - 1]))) {
        end--;
    }
    return s.substr(start, end - start);
}

std::string stripComment(const std::string& s) {
    size_t hash_pos = s.find('#');
    size_t slash_pos = s.find("//");
    size_t cut_pos = std::string::npos;
    if (hash_pos != std::string::npos) cut_pos = hash_pos;
    if (slash_pos != std::string::npos) {
        cut_pos = (cut_pos == std::string::npos) ? slash_pos : std::min(cut_pos, slash_pos);
    }
    if (cut_pos == std::string::npos) return s;
    return s.substr(0, cut_pos);
}

bool parseBinaryRow(const std::string& line,
                    std::vector<int>* row,
                    std::string* error) {
    if (row == nullptr || error == nullptr) return false;
    row->clear();

    std::string cleaned;
    cleaned.reserve(line.size());
    for (char ch : line) {
        if (ch == '0' || ch == '1') {
            cleaned.push_back(ch);
        } else if (std::isspace(static_cast<unsigned char>(ch)) || ch == ',') {
            continue;
        } else {
            *error = "non-binary character encountered";
            return false;
        }
    }

    if (cleaned.empty()) {
        *error = "empty binary row";
        return false;
    }

    row->reserve(cleaned.size());
    for (char bit : cleaned) {
        row->push_back(bit == '1' ? 1 : 0);
    }

    return true;
}

bool readBinaryRows(const std::string& path,
                    std::vector<std::vector<int>>* rows,
                    std::string* error) {
    if (rows == nullptr || error == nullptr) return false;
    rows->clear();

    std::ifstream in(path);
    if (!in.is_open()) {
        *error = "cannot open file: " + path;
        return false;
    }

    std::string line;
    int cols = -1;
    int line_no = 0;
    while (std::getline(in, line)) {
        line_no++;
        const std::string stripped = trim(stripComment(line));
        if (stripped.empty()) continue;

        std::vector<int> row;
        std::string row_err;
        if (!parseBinaryRow(stripped, &row, &row_err)) {
            std::ostringstream oss;
            oss << "line " << line_no << ": " << row_err;
            *error = oss.str();
            rows->clear();
            return false;
        }

        if (cols < 0) {
            cols = static_cast<int>(row.size());
        } else if (static_cast<int>(row.size()) != cols) {
            std::ostringstream oss;
            oss << "line " << line_no << ": expected " << cols
                << " columns, got " << row.size();
            *error = oss.str();
            rows->clear();
            return false;
        }

        rows->push_back(std::move(row));
    }

    if (rows->empty()) {
        *error = "no binary rows found in file";
        return false;
    }

    return true;
}

} // namespace

bool loadBinaryMatrixFromFile(const std::string& path,
                              BinaryMatrix* out,
                              std::string* error) {
    if (out == nullptr || error == nullptr) return false;

    std::vector<std::vector<int>> rows;
    if (!readBinaryRows(path, &rows, error)) {
        return false;
    }

    const int r = static_cast<int>(rows.size());
    const int c = static_cast<int>(rows.front().size());
    BinaryMatrix matrix(r, c);
    for (int i = 0; i < r; ++i) {
        for (int j = 0; j < c; ++j) {
            matrix.set(i, j, rows[i][j]);
        }
    }

    *out = std::move(matrix);
    return true;
}

bool loadBinaryVectorFromFile(const std::string& path,
                              std::vector<int>* out,
                              std::string* error) {
    if (out == nullptr || error == nullptr) return false;

    std::vector<std::vector<int>> rows;
    if (!readBinaryRows(path, &rows, error)) {
        return false;
    }
    if (rows.size() != 1) {
        std::ostringstream oss;
        oss << "expected exactly 1 row, got " << rows.size();
        *error = oss.str();
        return false;
    }

    *out = std::move(rows.front());
    return true;
}

bool loadDoubleVectorFromFile(const std::string& path,
                              std::vector<double>* out,
                              std::string* error) {
    if (out == nullptr || error == nullptr) return false;
    out->clear();

    std::ifstream in(path);
    if (!in.is_open()) {
        *error = "cannot open file: " + path;
        return false;
    }

    std::string line;
    int line_no = 0;
    while (std::getline(in, line)) {
        line_no++;
        std::string stripped = trim(stripComment(line));
        if (stripped.empty()) continue;
        for (char& ch : stripped) {
            if (ch == ',') ch = ' ';
        }
        std::istringstream iss(stripped);
        double v = 0.0;
        while (iss >> v) {
            out->push_back(v);
        }
        if (iss.fail() && !iss.eof()) {
            std::ostringstream oss;
            oss << "line " << line_no << ": invalid double value";
            *error = oss.str();
            out->clear();
            return false;
        }
    }

    if (out->empty()) {
        *error = "no numeric values found in file";
        return false;
    }
    return true;
}
