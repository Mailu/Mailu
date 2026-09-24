const path = require('path');
const webpack = require('webpack');
const css = require('mini-css-extract-plugin');
const mini = require('css-minimizer-webpack-plugin');
const terse = require('terser-webpack-plugin');
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
                test: /\.js$/,
                use: ['babel-loader'],
            },
            {
                test: /\.s?css$/i,
                use: [css.loader, 'css-loader', {
                    loader: 'sass-loader',
                    // admin-lte and the bootstrap it bundles are written
                    // against sass syntax that later dart-sass drops. Nothing
                    // in this repository can fix that, and the entry point is
                    // itself in node_modules, so quietDeps does not cover it.
                    options: { sassOptions: { silenceDeprecations: [
                        'import', 'slash-div', 'color-functions', 'global-builtin',
                        'abs-percent', 'if-function',
                    ] } },
                }],
            },
            {
                test: /\.less$/i,
                use: [css.loader, 'css-loader', 'less-loader'],
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
        new webpack.ProvidePlugin({
            $: 'jquery',
            jQuery: 'jquery',
            ClipboardJS: 'clipboard',
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
            new terse(),
            new mini({
                minimizerOptions: {
                    preset: [
                        'default', {
                            discardComments: { removeAll: true },
                        },
                    ],
                },
            }),
        ],
    },
};
