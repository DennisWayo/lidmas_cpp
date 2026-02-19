#pragma once
#include <fstream>
#include <string>

class CSVWriter {
public:
    CSVWriter(const std::string& filename,
              const std::string& header = "p,success_rate,avg_iterations") {
        file_.open(filename);
        file_ << header << "\n";
        file_.flush();
    }

    void write(double p,
               double success,
               double avg_iter) {
        file_ << p << ","
              << success << ","
              << avg_iter << "\n";
        file_.flush();
    }

    void writeCurve(double p,
                    double ber,
                    double fer,
                    double avg_iter) {
        file_ << p << ","
              << ber << ","
              << fer << ","
              << avg_iter << "\n";
        file_.flush();
    }

    void writeCurve(double p,
                    double ber,
                    double fer,
                    double avg_iter,
                    double syndrome_sat_rate) {
        file_ << p << ","
              << ber << ","
              << fer << ","
              << avg_iter << ","
              << syndrome_sat_rate << "\n";
        file_.flush();
    }

    void writeCurve(double p,
                    double ber,
                    double fer,
                    double avg_iter,
                    double parity_sat_rate,
                    double max_iter_hit_rate) {
        file_ << p << ","
              << ber << ","
              << fer << ","
              << avg_iter << ","
              << parity_sat_rate << ","
              << max_iter_hit_rate << "\n";
        file_.flush();
    }

private:
    std::ofstream file_;
};
