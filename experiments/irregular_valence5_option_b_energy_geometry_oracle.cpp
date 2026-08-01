#include <algorithm>
#include <array>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <string>
#include <vector>

namespace
{
constexpr int F = 20, Q = 3, R = 7, S = 12, A = 3;
constexpr long double LegacyVolumeFactor = 0.16666666666L;
constexpr std::array<std::array<long double, 3>, Q> SamplePlan{{
    {{0.16666666666666666L, 0.16666666666666666L,
      0.33333333333333331L}},
    {{0.16666666666666666L, 0.66666666666666663L,
      0.33333333333333331L}},
    {{0.66666666666666663L, 0.16666666666666666L,
      0.33333333333333331L}},
}};
using Vec = std::array<long double, A>;
struct Package
{
    std::array<long double, 8> parameters{};
    std::array<long double, F> regularization{};
    std::array<Vec, S> coordinates{};
    std::array<std::array<int, 3>, F> faces{};
    std::array<std::array<std::array<long double, 3>, Q>, F> samples{};
    std::array<std::array<std::array<std::array<long double, S>, R>, Q>, F>
        rows{};
};

bool finite(long double value) { return std::isfinite(value); }
bool read(const std::string &path, Package &p)
{
    std::ifstream in(path);
    int f = 0, q = 0, r = 0, s = 0;
    if (!(in >> f >> q >> r >> s) || f != F || q != Q || r != R || s != S)
        return false;
    std::string tag;
    if (!(in >> tag) || tag != "PARAMETERS") return false;
    for (auto &x : p.parameters) if (!(in >> x) || !finite(x)) return false;
    if (!(in >> tag) || tag != "REGULARIZATION") return false;
    for (auto &x : p.regularization) if (!(in >> x) || !finite(x)) return false;
    int count = 0;
    if (!(in >> tag >> count) || tag != "COORDINATES" || count != S) return false;
    for (int source = 0; source < S; ++source)
    {
        int id = -1;
        if (!(in >> id) || id != source) return false;
        for (auto &x : p.coordinates[source]) if (!(in >> x) || !finite(x)) return false;
    }
    for (int face = 0; face < F; ++face)
    {
        int id = -1, ptex = -1;
        if (!(in >> tag >> id >> ptex) || tag != "FACE" || id != face || ptex != face) return false;
        for (int &source : p.faces[face]) if (!(in >> source) || source < 0 || source >= S) return false;
        for (int sample = 0; sample < Q; ++sample)
        {
            int sampleId = -1;
            if (!(in >> tag >> sampleId) || tag != "SAMPLE" || sampleId != sample) return false;
            for (auto &x : p.samples[face][sample]) if (!(in >> x) || !finite(x)) return false;
            if (p.samples[face][sample] != SamplePlan[sample]) return false;
            for (int row = 0; row < R; ++row)
            {
                int rowId = -1;
                if (!(in >> tag >> rowId) || tag != "ROW" || rowId != row) return false;
                for (auto &x : p.rows[face][sample][row]) if (!(in >> x) || !finite(x)) return false;
            }
        }
    }
    long double trailing = 0.0L;
    return !(in >> trailing);
}

Vec add(Vec a, const Vec &b) { for (int i=0;i<A;++i) a[i]+=b[i]; return a; }
Vec sub(Vec a, const Vec &b) { for (int i=0;i<A;++i) a[i]-=b[i]; return a; }
Vec scale(Vec a, long double x) { for (auto &v:a) v*=x; return a; }
long double dot(const Vec &a,const Vec &b){return a[0]*b[0]+a[1]*b[1]+a[2]*b[2];}
Vec cross(const Vec&a,const Vec&b){return {a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]};}
long double norm(const Vec&a){return std::sqrt(dot(a,a));}
Vec row_value(const std::array<long double,S>&row,const std::array<Vec,S>&coords)
{
    Vec out{};
    for(int source=0;source<S;++source) for(int axis=0;axis<A;++axis) out[axis]+=row[source]*coords[source][axis];
    return out;
}
void print(const std::vector<long double>&v)
{
    std::cout<<'[';
    for(std::size_t i=0;i<v.size();++i){if(i)std::cout<<',';std::cout<<v[i];}
    std::cout<<']';
}
} // namespace

int main(int argc,char**argv)
{
    if(argc!=2){std::cerr<<"usage: oracle PACKAGE\n";return 2;}
    Package p;
    if(!read(argv[1],p)){std::cerr<<"invalid oracle package\n";return 3;}
    std::vector<long double> curvature,regularization,normals,mean,area,volume;
    bool ok=true;
    for(int face=0;face<F;++face)
    {
        long double e=0.0L,hmean=0.0L,a=0.0L,v=0.0L;
        Vec weightedNormal{};
        for(int sample=0;sample<Q;++sample)
        {
            std::array<Vec,R> d{};
            for(int row=0;row<R;++row)d[row]=row_value(p.rows[face][sample][row],p.coordinates);
            const Vec xa=cross(d[1],d[2]);
            const long double sqa=norm(xa);
            if(!(sqa>0.0L)||!finite(sqa)){ok=false;continue;}
            const Vec xa1=add(cross(d[3],d[2]),cross(d[1],d[6]));
            const Vec xa2=add(cross(d[5],d[2]),cross(d[1],d[4]));
            const long double sqa1=dot(xa,xa1)/sqa;
            const long double sqa2=dot(xa,xa2)/sqa;
            const Vec unit=scale(xa,1.0L/sqa);
            const Vec a31=scale(sub(scale(xa1,sqa),scale(xa,sqa1)),1.0L/(sqa*sqa));
            const Vec a32=scale(sub(scale(xa2,sqa),scale(xa,sqa2)),1.0L/(sqa*sqa));
            const Vec reciprocal1=scale(cross(d[2],unit),1.0L/sqa);
            const Vec reciprocal2=scale(cross(unit,d[1]),1.0L/sqa);
            const long double h=0.5L*(dot(reciprocal1,a31)+dot(reciprocal2,a32));
            const long double weight=p.samples[face][sample][2];
            hmean+=0.5L*weight*h;
            e+=0.5L*weight*(0.5L*p.parameters[0]*sqa*std::pow(2.0L*h-p.parameters[1],2));
            weightedNormal=add(weightedNormal,scale(unit,0.5L*weight));
            a+=0.5L*weight*sqa;
            v+=LegacyVolumeFactor*weight*d[0][0]*xa[0];
        }
        const long double normalLength=norm(weightedNormal);
        if(!(normalLength>0.0L)||!finite(normalLength)) ok=false;
        const Vec unitNormal=normalLength>0.0L?scale(weightedNormal,1.0L/normalLength):Vec{};
        curvature.push_back(e);regularization.push_back(p.regularization[face]);
        mean.push_back(hmean);area.push_back(a);volume.push_back(v);
        normals.insert(normals.end(),unitNormal.begin(),unitNormal.end());
        ok=ok&&finite(e)&&finite(hmean)&&finite(a)&&finite(v)&&finite(unitNormal[0])&&finite(unitNormal[1])&&finite(unitNormal[2]);
    }
    std::cout<<std::setprecision(21)<<'{';
    std::cout<<"\"status\":\""<<(ok?"passed":"failed")<<"\",";
    std::cout<<"\"independent_long_double_oracle\":true,";
    std::cout<<"\"calls_element_energy_force_regular\":false,";
    std::cout<<"\"face_curvature_energy\":";print(curvature);
    std::cout<<",\"face_regularization_energy\":";print(regularization);
    std::cout<<",\"face_normals\":";print(normals);
    std::cout<<",\"face_mean_curvature\":";print(mean);
    std::cout<<",\"face_area\":";print(area);
    std::cout<<",\"face_legacy_volume\":";print(volume);
    std::cout<<"}\n";
    return ok?0:4;
}
