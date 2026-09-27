const path = require('path');
const css = require('mini-css-extract-plugin');
const mini = require('css-minimizer-webpack-plugin');
const compress = require('compression-webpack-plugin');

module.exports = {
    mode: 'production',
    entry: {
        app: {
            import: ['./assets/app.css', './assets/app.js'],
            dependOn: 'vendor',
        },
        vendor: './assets/vendor.js',
        logo: './assets/mailu.png',
    },
    output: {
        path: path.resolve(__dirname, 'static/'),
        filename: '[name].js',
        assetModuleFilename: '[name][ext]',
    },
    module: {
        rules: [
            {
                test: /\.s?css$/i,
                use: [css.loader, 'css-loader', {
                    loader: 'sass-loader',
                    // AdminLTE and Bootstrap still use deprecated Sass imports.
                    options: { sassOptions: { silenceDeprecations: [
                        'import', 'slash-div', 'color-functions', 'global-builtin',
                        'abs-percent', 'if-function',
                    ] } },
                }],
            },
            {
                test: /\.(json|png|svg|jpg|jpeg|gif)$/i,
                type: 'asset/resource',
            },
        ],
    },
    plugins: [
        new css({
            filename: '[name].css',
            chunkFilename: '[id].css',
        }),
        new compress({
            filename: '[path][base].gz',
            algorithm: "gzip",
            exclude: /\.(png|gif|jpe?g)$/,
            threshold: 5120,
            minRatio: 0.8,
            deleteOriginalAssets: false,
        }),
    ],
    optimization: {
        minimize: true,
        minimizer: [
            '...',
            new mini({
                minimizerOptions: {
                    preset: [
                        'default', {
                            discardComments: { removeAll: true },
                            svgo: false,
                        },
                    ],
                },
            }),
        ],
    },
};
